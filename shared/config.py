"""Environment configuration loading for the freight agent platform.

Reads settings from a .env file (via python-dotenv) and process environment
variables, and exposes them as a single typed Config object via get_config().
"""

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

from shared.errors import DataError


@dataclass(frozen=True)
class Config:
    """Typed application configuration loaded from environment variables."""

    anthropic_api_key: str
    database_path: str
    log_level: str
    fixtures_path: str


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Load and return the application Config, caching the result.

    Loads variables from a .env file in the current working directory (if
    present) and then reads ANTHROPIC_API_KEY, DATABASE_PATH, LOG_LEVEL, and
    FIXTURES_PATH from the environment.

    Raises:
        DataError: If ANTHROPIC_API_KEY is not set.
    """
    load_dotenv()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or api_key == "your_key_here":
        raise DataError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and "
            "fill in a real Anthropic API key."
        )

    return Config(
        anthropic_api_key=api_key,
        database_path=os.getenv("DATABASE_PATH", "./data/freight.db"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        fixtures_path=os.getenv("FIXTURES_PATH", "./fixtures"),
    )
