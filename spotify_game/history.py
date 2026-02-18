import json
from typing import Any

from .config import GAME_HISTORY_PATH


def append_game_history(summary: dict[str, Any]) -> None:
    with GAME_HISTORY_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(summary) + "\n")

