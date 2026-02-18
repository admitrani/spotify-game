import random
import time
from typing import Any

import spotipy
from spotipy.exceptions import SpotifyException

MIN_SNIPPET_REMAINING_MARGIN_MS = 1500
FULL_SNIPPET_WINDOW_ERROR = "Could not start track with enough remaining time for full snippet."


def remaining_ms_for_track(playback_state: dict[str, Any], track_uri: str) -> int | None:
    item = playback_state.get("item")
    progress_ms = playback_state.get("progress_ms")
    if not isinstance(item, dict) or not isinstance(progress_ms, int):
        return None

    live_uri = item.get("uri")
    live_duration_ms = item.get("duration_ms")
    if live_uri != track_uri or not isinstance(live_duration_ms, int):
        return None

    return live_duration_ms - progress_ms


def has_enough_remaining_window(
    sp: spotipy.Spotify,
    track_uri: str,
    required_remaining_ms: int,
) -> bool:
    for attempt in range(3):
        playback_state = sp.current_playback()
        if isinstance(playback_state, dict):
            remaining_ms = remaining_ms_for_track(playback_state, track_uri)
            if isinstance(remaining_ms, int):
                return remaining_ms >= required_remaining_ms

        # Fallback only on last check to reduce extra network calls.
        if attempt == 2:
            playback_state = sp.current_user_playing_track()
            if isinstance(playback_state, dict):
                remaining_ms = remaining_ms_for_track(playback_state, track_uri)
                if isinstance(remaining_ms, int):
                    return remaining_ms >= required_remaining_ms

        time.sleep(0.06)

    return False


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
    duration_ms = track.get("duration_ms", 0)
    if not isinstance(duration_ms, int):
        duration_ms = 0

    if duration_ms < snippet_ms:
        return False, "Track is shorter than the selected snippet length."

    last_error: str | None = None
    for _ in range(3):
        # Keep at least a small safety margin from the tail to absorb position drift.
        max_start_ms = max(0, duration_ms - snippet_ms - MIN_SNIPPET_REMAINING_MARGIN_MS)
        start_position_ms = random.randint(0, max_start_ms) if max_start_ms else 0

        try:
            sp.transfer_playback(device_id=device_id, force_play=False)
            sp.start_playback(
                uris=[track["uri"]],
                device_id=device_id,
                position_ms=start_position_ms,
            )

            if has_enough_remaining_window(
                sp=sp,
                track_uri=track["uri"],
                required_remaining_ms=snippet_ms - MIN_SNIPPET_REMAINING_MARGIN_MS,
            ):
                return True, None

            last_error = FULL_SNIPPET_WINDOW_ERROR
            continue
        except SpotifyException as exc:
            last_error = str(exc)
            time.sleep(0.4)

    if last_error == FULL_SNIPPET_WINDOW_ERROR:
        return False, FULL_SNIPPET_WINDOW_ERROR
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
