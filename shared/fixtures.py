"""Fixture loading helpers shared by every agent in the freight platform.

Fixtures are the only source of test/demo data in v1 — no real external API
calls are made. Paths are resolved relative to FIXTURES_PATH so agents never
hardcode absolute paths.
"""

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from shared.errors import DataError

load_dotenv()


def _fixtures_root() -> Path:
    """Return the configured fixtures root directory as a Path."""
    return Path(os.getenv("FIXTURES_PATH", "./fixtures"))


def load_json(path: str | Path) -> Any:
    """Load and parse a JSON file.

    Args:
        path: Path to a JSON file, absolute or relative to the current
            working directory.

    Returns:
        The parsed JSON content (dict or list).

    Raises:
        DataError: If the file does not exist or contains invalid JSON.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise DataError(f"Fixture file not found: {file_path}")
    try:
        with file_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise DataError(f"Invalid JSON in fixture file {file_path}: {exc}") from exc


def load_fixtures(agent_name: str, filename: str) -> Any:
    """Load a fixture file belonging to a specific agent.

    Resolves to <FIXTURES_PATH>/<agent_name>/<filename>.

    Args:
        agent_name: Name of the agent's fixtures subfolder, e.g. "load_matching".
        filename: Fixture file name, e.g. "loads.json".

    Returns:
        The parsed JSON content (dict or list).

    Raises:
        DataError: If the file does not exist or contains invalid JSON.
    """
    return load_json(_fixtures_root() / agent_name / filename)
