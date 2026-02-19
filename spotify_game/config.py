"""Shared configuration constants used across the application."""

from pathlib import Path

# Spotify OAuth scopes needed for reading library and controlling playback.
SCOPE = "user-library-read user-read-playback-state user-modify-playback-state"

# Local file paths for auth token caching, library cache, and game history.
TOKEN_CACHE_PATH = Path(".spotifycache")
LEGACY_TOKEN_CACHE_PATH = Path(".cache")
LIBRARY_CACHE_PATH = Path("library_data.json")
GAME_HISTORY_PATH = Path("game_history.jsonl")

# Runtime tuning constants.
SAVED_TRACKS_PAGE_SIZE = 50  # Spotify API max page size for saved tracks.
OPTION_COUNT = 4
DEFAULT_SNIPPET_SECONDS = 15
MAX_TERMINAL_WIDTH = 110
