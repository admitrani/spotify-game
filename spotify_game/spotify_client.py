"""Spotipy client setup and cleanup helpers."""

import logging

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from .config import SCOPE, TOKEN_CACHE_PATH
from .env import get_required_env


def configure_spotipy_logging() -> None:
    """Reduce Spotipy logger noise so gameplay output stays readable."""
    for logger_name in ("spotipy", "spotipy.client", "spotipy.oauth2"):
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.CRITICAL)
        logger.propagate = False


# Apply logging policy at import so all consumers get consistent behavior.
configure_spotipy_logging()


def create_spotify_client() -> spotipy.Spotify:
    """Create an authenticated Spotipy client with retries and timeouts."""
    # SpotifyOAuth handles browser auth flow, token refresh, and cache management.
    auth_manager = SpotifyOAuth(
        client_id=get_required_env("SPOTIPY_CLIENT_ID"),
        client_secret=get_required_env("SPOTIPY_CLIENT_SECRET"),
        redirect_uri=get_required_env("SPOTIPY_REDIRECT_URI"),
        scope=SCOPE,
        cache_path=str(TOKEN_CACHE_PATH),
        open_browser=True,
        show_dialog=False,
    )

    return spotipy.Spotify(
        auth_manager=auth_manager,
        requests_timeout=10,
        retries=3,
        status_retries=3,
    )


def close_sessions(sp: spotipy.Spotify) -> None:
    """Close HTTP sessions held by Spotipy objects."""
    for obj in (sp, sp.auth_manager):
        # Spotipy exposes sessions on private attributes; close defensively.
        session = getattr(obj, "_session", None)
        close_fn = getattr(session, "close", None)
        if callable(close_fn):
            close_fn()
