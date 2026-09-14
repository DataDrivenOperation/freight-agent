"""Custom exception hierarchy shared by every agent in the freight platform.

All agent code raises one of these instead of a bare Exception, so callers
(and the CLI layer) can catch a single AgentError and still tell failure
modes apart.
"""


class AgentError(Exception):
    """Base class for every exception raised by agent code in this platform."""


class LLMError(AgentError):
    """Raised when a call to Claude fails after all retries are exhausted."""


class DataError(AgentError):
    """Raised when fixture or persisted data is missing, malformed, or unreadable."""


class ValidationError(AgentError):
    """Raised when data (including an LLM response) fails Pydantic schema validation."""


class HumanReviewRequired(AgentError):
    """Raised when a result's confidence is too low to act on without human review."""
