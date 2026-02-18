import random
import time
from datetime import datetime, timezone
from typing import Any

import spotipy

from .config import GAME_HISTORY_PATH, OPTION_COUNT
from .history import append_game_history, get_high_score
from .playback import (
    FULL_SNIPPET_WINDOW_ERROR,
    pause_playback,
    play_random_snippet,
    resolve_device,
)
from .ui import (
    build_answer_prompt,
    build_option_lines,
    build_round_lines,
    enter_alternate_screen,
    get_terminal_width,
    leave_alternate_screen,
    render_round_screen,
    timed_choice_prompt,
    update_round_timer,
)


def build_options(correct_track: dict[str, Any], library: list[dict[str, Any]]) -> list[dict[str, Any]]:
    alternatives = [track for track in library if track["uri"] != correct_track["uri"]]
    sampled = random.sample(alternatives, OPTION_COUNT - 1)
    options = sampled + [correct_track]
    random.shuffle(options)
    return options


def play_game(
    sp: spotipy.Spotify,
    library: list[dict[str, Any]],
    snippet_seconds: int,
    max_rounds: int,
) -> None:
    if len(library) < OPTION_COUNT:
        raise RuntimeError(f"Need at least {OPTION_COUNT} tracks in your library to play.")

    previous_high_score = get_high_score()

    device_id = resolve_device(sp)
    if not device_id:
        raise RuntimeError("No available Spotify devices. Open Spotify on any device and try again.")

    score = 0
    attempts = 0
    started_at = time.time()
    alternate_screen_enabled = enter_alternate_screen()
    end_message: str | None = None
    last_status = ""
    last_round_option_blocks: list[list[str]] = []
    last_round_option_count = OPTION_COUNT

    try:
        try:
            while True:
                if max_rounds and attempts >= max_rounds:
                    end_message = "Reached round limit."
                    last_status = "limit"
                    break

                device_id = resolve_device(sp, preferred_device_id=device_id)
                if not device_id:
                    end_message = "No available playback device found."
                    last_status = "error"
                    break

                current_track = random.choice(library)
                options = build_options(current_track, library)
                terminal_width = get_terminal_width()
                option_blocks = [
                    build_option_lines(index=i, track=track, width=terminal_width)
                    for i, track in enumerate(options, start=1)
                ]
                last_round_option_blocks = option_blocks
                last_round_option_count = len(options)

                render_round_screen(
                    score=score,
                    remaining_seconds=snippet_seconds,
                    option_blocks=option_blocks,
                    option_count=len(options),
                    answer_buffer="",
                )

                rendered_line_count = 5 + sum(len(block) + 1 for block in option_blocks)

                def render_callback(remaining_seconds: int, answer_buffer: str) -> None:
                    update_round_timer(
                        rendered_line_count=rendered_line_count,
                        option_count=len(options),
                        remaining_seconds=remaining_seconds,
                        answer_buffer=answer_buffer,
                    )

                played, playback_error = play_random_snippet(
                    sp=sp,
                    track=current_track,
                    device_id=device_id,
                    snippet_seconds=snippet_seconds,
                )
                if not played:
                    if playback_error == FULL_SNIPPET_WINDOW_ERROR:
                        continue
                    end_message = "Could not start playback on your active Spotify device."
                    if playback_error:
                        end_message = f"{end_message}\nSpotify error: {playback_error}"
                    last_status = "error"
                    break

                attempts += 1
                user_choice, status = timed_choice_prompt(
                    len(options),
                    timeout_seconds=snippet_seconds,
                    render_callback=render_callback,
                )
                pause_playback(sp, device_id)

                if status == "quit":
                    end_message = "Game ended by user."
                    last_status = "quit"
                    break

                if status == "timeout":
                    end_message = "Time ran out. Game over."
                    last_status = "timeout"
                    break

                if user_choice is None:
                    end_message = "No answer provided. Game over."
                    last_status = "invalid"
                    break

                selected_track = options[user_choice]
                if selected_track["uri"] == current_track["uri"]:
                    score += 1
                    continue

                artists = ", ".join(current_track["artists"])
                end_message = f"Incorrect. Correct answer: {current_track['name']} - {artists}"
                last_status = "incorrect"
                break
        finally:
            pause_playback(sp, device_id)
    finally:
        if alternate_screen_enabled:
            leave_alternate_screen()

    if end_message and last_status != "quit" and last_round_option_blocks:
        print("\n".join(build_round_lines(score=score, remaining_seconds=0, option_blocks=last_round_option_blocks)))
        print(build_answer_prompt(option_count=last_round_option_count))

    if end_message:
        print(end_message)

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

    is_new_high_score = score > previous_high_score
    high_score = max(previous_high_score, score)

    print("\nGame Over")
    if is_new_high_score:
        print(f"Final score: {score} (HIGH SCORE)")
        print("New high score!")
    else:
        print(f"Final score: {score}")
    print(f"High score: {high_score}")
    print(f"Run log appended to: {GAME_HISTORY_PATH}")
