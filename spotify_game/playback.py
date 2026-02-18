import random
import time
from typing import Any

import spotipy
from spotipy.exceptions import SpotifyException


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

    # Enforce full snippet playback: start point must be <= (duration - snippet).
    max_start_ms = duration_ms - snippet_ms
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
