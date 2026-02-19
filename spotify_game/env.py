"""Environment-variable helpers and token-cache migration utilities."""

import os
from pathlib import Path

from .config import LEGACY_TOKEN_CACHE_PATH, TOKEN_CACHE_PATH


def load_env_file(path: Path = Path(".env")) -> None:
    """Load simple KEY=VALUE pairs from a .env file into process env."""
    if not path.exists():
        return

    with path.open("r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            # Skip comments, blank lines, and malformed rows.
            if not line or line.startswith("#") or "=" not in line:
                continue

            # Split once so values containing '=' are preserved.
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip().strip("'\"")


def get_required_env(name: str) -> str:
    """Fetch a required environment variable or raise a clear error."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def migrate_legacy_token_cache() -> None:
    """Copy legacy token cache file to the current path when needed."""
    # Skip migration when there is nothing to migrate or target already exists.
    if not LEGACY_TOKEN_CACHE_PATH.exists() or TOKEN_CACHE_PATH.exists():
        return

    try:
        TOKEN_CACHE_PATH.write_text(LEGACY_TOKEN_CACHE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    except OSError:
        # Migration is best-effort; auth can still proceed normally.
        return
