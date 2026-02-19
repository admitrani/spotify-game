"""Run-history persistence and high-score aggregation helpers."""

import json
from typing import Any

from .config import GAME_HISTORY_PATH


def get_high_score() -> int:
    """Scan history file and return the highest recorded score."""
    if not GAME_HISTORY_PATH.exists():
        return 0

    high_score = 0
    try:
        with GAME_HISTORY_PATH.open("r", encoding="utf-8") as file:
            for raw_line in file:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    # Ignore malformed rows and continue scanning.
                    continue

                score = payload.get("score", 0)
                if isinstance(score, int):
                    high_score = max(high_score, score)
    except OSError:
        # Missing/unreadable history should not block gameplay.
        return 0

    return high_score


def append_game_history(summary: dict[str, Any]) -> None:
    """Append one game summary row in JSONL format."""
    with GAME_HISTORY_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(summary) + "\n")
