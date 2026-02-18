from pathlib import Path

SCOPE = "user-library-read user-read-playback-state user-modify-playback-state"
TOKEN_CACHE_PATH = Path(".spotifycache")
LEGACY_TOKEN_CACHE_PATH = Path(".cache")
LIBRARY_CACHE_PATH = Path("library_data.json")
GAME_HISTORY_PATH = Path("game_history.jsonl")

SAVED_TRACKS_PAGE_SIZE = 50  # Spotify API max page size for saved tracks.
OPTION_COUNT = 4
DEFAULT_SNIPPET_SECONDS = 15
MAX_TERMINAL_WIDTH = 110

