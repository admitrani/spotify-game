import logging

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from .config import SCOPE, TOKEN_CACHE_PATH
from .env import get_required_env


def configure_spotipy_logging() -> None:
    for logger_name in ("spotipy", "spotipy.client", "spotipy.oauth2"):
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.CRITICAL)
        logger.propagate = False


configure_spotipy_logging()


def create_spotify_client() -> spotipy.Spotify:
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
    for obj in (sp, sp.auth_manager):
        session = getattr(obj, "_session", None)
        close_fn = getattr(session, "close", None)
        if callable(close_fn):
            close_fn()

