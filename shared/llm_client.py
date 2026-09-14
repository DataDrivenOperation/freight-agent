"""Single wrapper around the Anthropic SDK. Every LLM call in this platform
goes through call_claude() so logging, retries, and schema validation are
handled in exactly one place.
"""

import json
import time
from typing import Any, Type, TypeVar

from anthropic import Anthropic
from pydantic import BaseModel, ValidationError as PydanticValidationError

from shared.config import get_config
from shared.errors import LLMError, ValidationError as AgentValidationError
from shared.logging import get_logger

logger = get_logger("llm_client")

_RETRY_DELAYS_SECONDS = (1, 2)

# Rough per-million-token pricing used only to log a cost estimate.
_COST_PER_MTOK_INPUT_USD = 3.0
_COST_PER_MTOK_OUTPUT_USD = 15.0

SchemaT = TypeVar("SchemaT", bound=BaseModel)


def _estimate_cost_usd(input_chars: int, output_chars: int) -> float:
    """Estimate call cost in USD from character counts (rough proxy for tokens).

    Uses ~4 characters per token as a standard approximation.
    """
    input_tokens = input_chars / 4
    output_tokens = output_chars / 4
    return (input_tokens / 1_000_000) * _COST_PER_MTOK_INPUT_USD + (
        output_tokens / 1_000_000
    ) * _COST_PER_MTOK_OUTPUT_USD


def call_claude(
    prompt: str,
    system: str | None = None,
    schema: Type[SchemaT] | None = None,
    model: str = "claude-sonnet-4-5",
    max_tokens: int = 4096,
) -> dict[str, Any] | SchemaT:
    """Call Claude and return its response, optionally validated against a schema.

    Retries up to 2 times (1s, then 2s backoff) on transient failures before
    raising. If `schema` is given, the response is parsed as JSON and
    validated against it; the returned value is a schema instance rather
    than a raw dict.

    Args:
        prompt: The user prompt to send.
        system: Optional system prompt.
        schema: Optional Pydantic model class to validate the JSON response.
        model: Anthropic model id to call.
        max_tokens: Maximum tokens to generate.

    Returns:
        The parsed JSON response as a dict, or a `schema` instance if a
        schema was provided.

    Raises:
        LLMError: If the call fails after all retries.
        ValidationError: If the response does not match `schema`.
    """
    config = get_config()
    client = Anthropic(api_key=config.anthropic_api_key)

    last_error: Exception | None = None
    for attempt in range(len(_RETRY_DELAYS_SECONDS) + 1):
        started_at = time.time()
        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system:
                kwargs["system"] = system

            response = client.messages.create(**kwargs)
            response_text = "".join(
                block.text for block in response.content if block.type == "text"
            )

            logger.info(
                json.dumps(
                    {
                        "event": "llm_call",
                        "model": model,
                        "prompt_chars": len(prompt),
                        "response_chars": len(response_text),
                        "duration_seconds": round(time.time() - started_at, 3),
                        "cost_estimate_usd": round(
                            _estimate_cost_usd(len(prompt), len(response_text)), 6
                        ),
                    }
                )
            )

            return _parse_response(response_text, schema)

        except AgentValidationError:
            raise
        except Exception as exc:  # noqa: BLE001 - any SDK/network failure is retryable
            last_error = exc
            logger.warning(f"LLM call attempt {attempt + 1} failed: {exc}")
            if attempt < len(_RETRY_DELAYS_SECONDS):
                time.sleep(_RETRY_DELAYS_SECONDS[attempt])

    raise LLMError(f"Claude call failed after retries: {last_error}") from last_error


def _parse_response(
    response_text: str, schema: Type[SchemaT] | None
) -> dict[str, Any] | SchemaT:
    """Parse response text as JSON and optionally validate it against a schema.

    Raises:
        ValidationError: If the text is not valid JSON, or fails schema validation.
    """
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise AgentValidationError(
            f"Claude response was not valid JSON: {exc}"
        ) from exc

    if schema is None:
        return data

    try:
        return schema.model_validate(data)
    except PydanticValidationError as exc:
        raise AgentValidationError(
            f"Claude response did not match schema {schema.__name__}: {exc}"
        ) from exc
