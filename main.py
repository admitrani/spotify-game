import argparse
import json
import logging
import math
import os
import random
import select
import shutil
import sys
import time
import urllib.request
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
import textwrap

import spotipy
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOAuth

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import termios
    import tty
except ImportError:
    termios = None
    tty = None


SCOPE = "user-library-read user-read-playback-state user-modify-playback-state"
TOKEN_CACHE_PATH = ".spotifycache"
LIBRARY_CACHE_PATH = Path("library_data.json")
GAME_HISTORY_PATH = Path("game_history.jsonl")
SAVED_TRACKS_PAGE_SIZE = 50  # Spotify API max page size for saved tracks.
OPTION_COUNT = 4
DEFAULT_SNIPPET_SECONDS = 15
ASCII_PALETTE = ".:-=+*#%@"

ASCII_ART_CACHE: dict[str, list[str]] = {}


def configure_spotipy_logging() -> None:
    for logger_name in ("spotipy", "spotipy.client", "spotipy.oauth2"):
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.CRITICAL)
        logger.propagate = False


configure_spotipy_logging()


def load_env_file(path: Path = Path(".env")) -> None:
    if not path.exists():
        return

    with path.open("r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip().strip("'\"")


def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def migrate_legacy_token_cache() -> None:
    legacy_cache = Path(".cache")
    modern_cache = Path(TOKEN_CACHE_PATH)

    if not legacy_cache.exists() or modern_cache.exists():
        return

    try:
        modern_cache.write_text(legacy_cache.read_text(encoding="utf-8"), encoding="utf-8")
    except OSError:
        return


def create_spotify_client() -> spotipy.Spotify:
    auth_manager = SpotifyOAuth(
        client_id=get_required_env("SPOTIPY_CLIENT_ID"),
        client_secret=get_required_env("SPOTIPY_CLIENT_SECRET"),
        redirect_uri=get_required_env("SPOTIPY_REDIRECT_URI"),
        scope=SCOPE,
        cache_path=TOKEN_CACHE_PATH,
        open_browser=True,
        show_dialog=False,
    )

    return spotipy.Spotify(
        auth_manager=auth_manager,
        requests_timeout=10,
        retries=3,
        status_retries=3,
    )


def extract_image_url(raw_track: dict[str, Any]) -> str | None:
    existing_image = raw_track.get("image_url")
    if isinstance(existing_image, str) and existing_image:
        return existing_image

    album = raw_track.get("album")
    if not isinstance(album, dict):
        return None

    images = album.get("images")
    if not isinstance(images, list) or not images:
        return None

    for image in reversed(images):
        if isinstance(image, dict):
            url = image.get("url")
            if isinstance(url, str) and url:
                return url

    return None


def normalize_track(raw_track: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(raw_track, dict):
        return None

    uri = raw_track.get("uri")
    if not uri:
        return None

    raw_artists = raw_track.get("artists", [])
    artists: list[str] = []
    if isinstance(raw_artists, list):
        if raw_artists and isinstance(raw_artists[0], str):
            artists = [artist for artist in raw_artists if artist]
        else:
            artists = [artist.get("name", "").strip() for artist in raw_artists if isinstance(artist, dict)]
            artists = [artist for artist in artists if artist]

    if not artists:
        artists = ["Unknown Artist"]

    duration_ms = raw_track.get("duration_ms", 0)
    if not isinstance(duration_ms, int):
        duration_ms = 0

    return {
        "uri": uri,
        "name": str(raw_track.get("name", "Unknown Track")),
        "artists": artists,
        "duration_ms": duration_ms,
        "image_url": extract_image_url(raw_track),
    }


def fetch_library_from_spotify(sp: spotipy.Spotify) -> list[dict[str, Any]]:
    tracks: list[dict[str, Any]] = []
    offset = 0

    while True:
        page = sp.current_user_saved_tracks(limit=SAVED_TRACKS_PAGE_SIZE, offset=offset)
        items = page.get("items", [])
        if not items:
            break

        for item in items:
            track = normalize_track(item.get("track"))
            if track:
                tracks.append(track)

        offset += len(items)
        print(f"\rSyncing Spotify library: {len(tracks)} tracks", end="", flush=True)

    print()

    seen_uris: set[str] = set()
    deduplicated: list[dict[str, Any]] = []
    for track in tracks:
        uri = track["uri"]
        if uri in seen_uris:
            continue
        seen_uris.add(uri)
        deduplicated.append(track)

    return deduplicated


def load_library_cache() -> list[dict[str, Any]]:
    if not LIBRARY_CACHE_PATH.exists():
        return []

    try:
        with LIBRARY_CACHE_PATH.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except (json.JSONDecodeError, OSError):
        return []

    if isinstance(payload, dict):
        raw_tracks = payload.get("tracks", [])
    elif isinstance(payload, list):
        raw_tracks = payload
    else:
        return []

    tracks: list[dict[str, Any]] = []
    for entry in raw_tracks:
        if isinstance(entry, dict) and "track" in entry:
            track = normalize_track(entry.get("track"))
        else:
            track = normalize_track(entry if isinstance(entry, dict) else None)

        if track:
            tracks.append(track)

    return tracks


def save_library_cache(tracks: list[dict[str, Any]]) -> None:
    payload = {
        "synced_at_utc": datetime.now(timezone.utc).isoformat(),
        "track_count": len(tracks),
        "tracks": tracks,
    }

    with LIBRARY_CACHE_PATH.open("w", encoding="utf-8") as file:
        json.dump(payload, file)


def load_or_sync_library(sp: spotipy.Spotify, refresh_library: bool) -> list[dict[str, Any]]:
    if not refresh_library:
        cached_tracks = load_library_cache()
        if cached_tracks:
            print(f"Loaded {len(cached_tracks)} tracks from cache. Use --refresh-library to resync.")
            return cached_tracks

    print("Refreshing saved tracks from Spotify...")
    tracks = fetch_library_from_spotify(sp)
    save_library_cache(tracks)
    print(f"Saved {len(tracks)} tracks to {LIBRARY_CACHE_PATH}.")
    return tracks


def resolve_device(sp: spotipy.Spotify, preferred_device_id: str | None = None) -> str | None:
    devices = sp.devices().get("devices", [])
    if not devices:
        return None

    if preferred_device_id:
        for device in devices:
            if device.get("id") == preferred_device_id and not device.get("is_restricted", False):
                return preferred_device_id

    for device in devices:
        if device.get("is_active") and not device.get("is_restricted", False):
            return device.get("id")

    for device in devices:
        if not device.get("is_restricted", False):
            return device.get("id")

    return None


def play_random_snippet(
    sp: spotipy.Spotify,
    track: dict[str, Any],
    device_id: str,
    snippet_seconds: int,
) -> tuple[bool, str | None]:
    snippet_ms = max(1, snippet_seconds) * 1000
    duration_ms = max(int(track.get("duration_ms", 0)), snippet_ms)
    max_start_ms = max(0, duration_ms - snippet_ms)
    start_position_ms = random.randint(0, max_start_ms) if max_start_ms else 0

    last_error: str | None = None
    for _ in range(2):
        try:
            sp.transfer_playback(device_id=device_id, force_play=False)
            sp.start_playback(
                uris=[track["uri"]],
                device_id=device_id,
                position_ms=start_position_ms,
            )
            return True, None
        except SpotifyException as exc:
            last_error = str(exc)
            time.sleep(0.4)

    return False, last_error


def pause_playback(sp: spotipy.Spotify, device_id: str | None) -> None:
    if device_id:
        try:
            sp.pause_playback(device_id=device_id)
            return
        except SpotifyException:
            pass

    try:
        sp.pause_playback()
    except SpotifyException:
        pass


def build_options(correct_track: dict[str, Any], library: list[dict[str, Any]]) -> list[dict[str, Any]]:
    alternatives = [track for track in library if track["uri"] != correct_track["uri"]]
    sampled = random.sample(alternatives, OPTION_COUNT - 1)
    options = sampled + [correct_track]
    random.shuffle(options)
    return options


def hydrate_missing_artwork(sp: spotipy.Spotify, tracks: list[dict[str, Any]]) -> bool:
    updated = False
    for track in tracks:
        if track.get("image_url"):
            continue

        try:
            details = sp.track(track["uri"])
        except SpotifyException:
            continue

        image_url = extract_image_url(details)
        if image_url:
            track["image_url"] = image_url
            updated = True

    return updated


def render_ascii_art(image_url: str | None, width: int = 24) -> list[str]:
    if not image_url or Image is None:
        return []

    if image_url in ASCII_ART_CACHE:
        return ASCII_ART_CACHE[image_url]

    try:
        with urllib.request.urlopen(image_url, timeout=6) as response:
            image_bytes = response.read()

        with Image.open(BytesIO(image_bytes)) as img:
            grayscale = img.convert("L")
            height = max(6, int((grayscale.height / max(1, grayscale.width)) * width * 0.55))
            resized = grayscale.resize((width, height))
            pixels = list(resized.getdata())

        palette_size = len(ASCII_PALETTE) - 1
        lines: list[str] = []
        for row in range(height):
            row_pixels = pixels[row * width : (row + 1) * width]
            line = "".join(ASCII_PALETTE[(pixel * palette_size) // 255] for pixel in row_pixels)
            lines.append(line)

        ASCII_ART_CACHE[image_url] = lines
        return lines
    except Exception:
        return []


def clear_terminal() -> None:
    if not sys.stdout.isatty():
        return

    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def build_option_lines(index: int, track: dict[str, Any], show_artwork: bool, width: int) -> list[str]:
    lines: list[str] = []
    title_width = max(30, width - 8)
    artist_width = max(30, width - 12)

    title_lines = textwrap.wrap(
        track["name"],
        width=title_width,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [track["name"]]
    lines.append(f"[{index}] {title_lines[0]}")
    for continuation in title_lines[1:]:
        lines.append(f"    {continuation}")

    artists_text = ", ".join(track["artists"])
    artist_lines = textwrap.wrap(
        artists_text,
        width=artist_width,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [artists_text]
    for artist_line in artist_lines:
        lines.append(f"    {artist_line}")

    if show_artwork:
        art_lines = render_ascii_art(track.get("image_url"))
        if art_lines:
            lines.extend(f"    {line}" for line in art_lines)
        else:
            lines.append("    [Artwork unavailable]")

    return lines


def render_round_screen(
    score: int,
    remaining_seconds: int,
    option_blocks: list[list[str]],
    option_count: int,
    answer_buffer: str = "",
) -> None:
    width = min(110, shutil.get_terminal_size(fallback=(110, 24)).columns)
    divider = "=" * width
    lines: list[str] = [
        divider,
        f"Score: {score}",
        f"Time left: {remaining_seconds:02d}s",
        divider,
    ]

    for block in option_blocks:
        lines.extend(block)
        lines.append("")

    lines.append(divider)

    clear_terminal()
    print("\n".join(lines))
    sys.stdout.write(f"Answer [1-{option_count}, q to quit] -> {answer_buffer}")
    sys.stdout.flush()


def parse_choice(raw_value: str, option_count: int) -> tuple[int | None, str]:
    if raw_value in {"q", "quit", "exit"}:
        return None, "quit"

    if raw_value.isdigit():
        choice = int(raw_value)
        if 1 <= choice <= option_count:
            return choice - 1, "answered"

    return None, "invalid"


def timed_choice_prompt(
    option_count: int,
    timeout_seconds: int,
    render_callback,
) -> tuple[int | None, str]:
    timeout_seconds = max(1, timeout_seconds)

    if not sys.stdin.isatty() or termios is None or tty is None:
        render_callback(timeout_seconds, "")
        print()
        choice, status = parse_choice(input(f"Answer [1-{option_count}, q to quit] -> ").strip().lower(), option_count)
        return choice, status

    fd = sys.stdin.fileno()
    old_attrs = termios.tcgetattr(fd)
    typed = ""
    deadline = time.monotonic() + timeout_seconds
    last_remaining = -1

    try:
        tty.setcbreak(fd)

        while True:
            remaining = max(0, int(math.ceil(deadline - time.monotonic())))
            if remaining != last_remaining:
                render_callback(remaining, typed)
                last_remaining = remaining

            if remaining <= 0:
                print()
                return None, "timeout"

            wait_seconds = min(0.1, max(0.0, deadline - time.monotonic()))
            try:
                ready, _, _ = select.select([sys.stdin], [], [], wait_seconds)
            except (OSError, ValueError):
                print()
                choice, status = parse_choice(input(f"Answer [1-{option_count}, q to quit] -> ").strip().lower(), option_count)
                return choice, status

            if not ready:
                continue

            char = sys.stdin.read(1)
            if char in ("\n", "\r"):
                print()
                choice, status = parse_choice(typed.strip().lower(), option_count)
                if status == "invalid":
                    print("Invalid choice. Enter a valid option number.")
                    time.sleep(0.8)
                    typed = ""
                    last_remaining = -1
                    continue
                return choice, status

            if char in ("\x7f", "\b"):
                typed = typed[:-1]
                render_callback(remaining, typed)
                continue

            if char.isprintable():
                typed += char
                render_callback(remaining, typed)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)


def append_game_history(summary: dict[str, Any]) -> None:
    with GAME_HISTORY_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(summary) + "\n")


def close_sessions(sp: spotipy.Spotify) -> None:
    for obj in (sp, sp.auth_manager):
        session = getattr(obj, "_session", None)
        close_fn = getattr(session, "close", None)
        if callable(close_fn):
            close_fn()


def play_game(
    sp: spotipy.Spotify,
    library: list[dict[str, Any]],
    snippet_seconds: int,
    max_rounds: int,
    show_artwork: bool,
) -> None:
    if len(library) < OPTION_COUNT:
        raise RuntimeError(f"Need at least {OPTION_COUNT} tracks in your library to play.")

    if show_artwork and Image is None:
        print("Pillow is not installed; artwork is disabled. Install it with `pip install Pillow`.")
        show_artwork = False

    device_id = resolve_device(sp)
    if not device_id:
        raise RuntimeError("No available Spotify devices. Open Spotify on any device and try again.")

    score = 0
    attempts = 0
    started_at = time.time()
    library_updated = False

    try:
        while True:
            if max_rounds and attempts >= max_rounds:
                print("\nReached round limit.")
                break

            device_id = resolve_device(sp, preferred_device_id=device_id)
            if not device_id:
                print("\nNo available playback device found.")
                break

            current_track = random.choice(library)
            options = build_options(current_track, library)

            if show_artwork and hydrate_missing_artwork(sp, options):
                library_updated = True

            terminal_width = min(110, shutil.get_terminal_size(fallback=(110, 24)).columns)
            option_blocks = [
                build_option_lines(index=i, track=track, show_artwork=show_artwork, width=terminal_width)
                for i, track in enumerate(options, start=1)
            ]

            def render_callback(remaining_seconds: int, answer_buffer: str) -> None:
                render_round_screen(
                    score=score,
                    remaining_seconds=remaining_seconds,
                    option_blocks=option_blocks,
                    option_count=len(options),
                    answer_buffer=answer_buffer,
                )

            render_callback(snippet_seconds, "")

            played, playback_error = play_random_snippet(
                sp=sp,
                track=current_track,
                device_id=device_id,
                snippet_seconds=snippet_seconds,
            )
            if not played:
                print("Could not start playback on your active Spotify device.")
                if playback_error:
                    print(f"Spotify error: {playback_error}")
                break

            attempts += 1
            user_choice, status = timed_choice_prompt(
                len(options),
                timeout_seconds=snippet_seconds,
                render_callback=render_callback,
            )
            pause_playback(sp, device_id)

            if status == "quit":
                print("Game ended by user.")
                break

            if status == "timeout":
                print("Time ran out. Game over.")
                break

            if user_choice is None:
                print("No answer provided. Game over.")
                break

            selected_track = options[user_choice]
            if selected_track["uri"] == current_track["uri"]:
                score += 1
                print("Correct.")
                continue

            artists = ", ".join(current_track["artists"])
            print(f"Incorrect. Correct answer: {current_track['name']} - {artists}")
            break
    finally:
        pause_playback(sp, device_id)

    if library_updated:
        save_library_cache(library)

    summary = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "attempts": attempts,
        "score": score,
        "accuracy_pct": round((score / attempts * 100), 2) if attempts else 0.0,
        "duration_seconds": round(time.time() - started_at, 2),
        "library_size": len(library),
        "snippet_seconds": snippet_seconds,
    }
    append_game_history(summary)

    print("\nGame Over")
    print(f"Final score: {score}")
    print(f"Run log appended to: {GAME_HISTORY_PATH}")


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
    parser.add_argument(
        "--no-artwork",
        action="store_true",
        help="Disable ASCII artwork rendering for option cards.",
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
        play_game(
            sp=sp,
            library=library,
            snippet_seconds=max(1, args.snippet_seconds),
            max_rounds=max(0, args.max_rounds),
            show_artwork=not args.no_artwork,
        )
    finally:
        close_sessions(sp)


if __name__ == "__main__":
    main()
