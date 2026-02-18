import json
from datetime import datetime, timezone
from typing import Any

import spotipy

from .config import LIBRARY_CACHE_PATH, SAVED_TRACKS_PAGE_SIZE


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

