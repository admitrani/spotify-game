import argparse

from .config import DEFAULT_SNIPPET_SECONDS
from .env import get_required_env, load_env_file, migrate_legacy_token_cache
from .game import play_game
from .library import load_or_sync_library
from .spotify_client import close_sessions, create_spotify_client
from .ui import prompt_play_again


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Spotify song guessing game")
    parser.add_argument(
        "--refresh-library",
        action="store_true",
        help="Re-fetch all saved tracks from Spotify and update local cache.",
    )
    parser.add_argument(
        "--snippet-seconds",
        type=int,
        default=DEFAULT_SNIPPET_SECONDS,
        help="Length of each snippet in seconds (default: 15).",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=0,
        help="Optional maximum rounds. 0 means unlimited.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_env_file()
    migrate_legacy_token_cache()

    redirect_uri = get_required_env("SPOTIPY_REDIRECT_URI")
    print(f"Using redirect URI: {redirect_uri}")

    sp = create_spotify_client()
    try:
        profile = sp.current_user()
        account_name = profile.get("display_name") or profile.get("id")
        print(f"Connected to Spotify account: {account_name}")

        library = load_or_sync_library(sp, refresh_library=args.refresh_library)
        snippet_seconds = max(1, args.snippet_seconds)
        max_rounds = max(0, args.max_rounds)

        while True:
            play_game(
                sp=sp,
                library=library,
                snippet_seconds=snippet_seconds,
                max_rounds=max_rounds,
            )
            if not prompt_play_again():
                break
    finally:
        close_sessions(sp)
