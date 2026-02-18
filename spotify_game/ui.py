import math
import select
import shutil
import sys
import textwrap
import time
from collections.abc import Callable

from .config import MAX_TERMINAL_WIDTH

try:
    import termios
    import tty
except ImportError:
    termios = None
    tty = None


def get_terminal_width() -> int:
    return min(MAX_TERMINAL_WIDTH, shutil.get_terminal_size(fallback=(MAX_TERMINAL_WIDTH, 24)).columns)


def clear_terminal() -> None:
    if not sys.stdout.isatty():
        return

    sys.stdout.write("\033[2J\033[3J\033[H")
    sys.stdout.flush()


def enter_alternate_screen() -> bool:
    if not sys.stdout.isatty():
        return False

    sys.stdout.write("\033[?1049h\033[H")
    sys.stdout.flush()
    return True


def leave_alternate_screen() -> None:
    if not sys.stdout.isatty():
        return

    sys.stdout.write("\033[?1049l")
    sys.stdout.flush()


def build_option_lines(index: int, track: dict, width: int) -> list[str]:
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

    return lines


def build_round_lines(
    score: int,
    remaining_seconds: int,
    option_blocks: list[list[str]],
) -> list[str]:
    width = get_terminal_width()
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
    return lines


def render_round_screen(
    score: int,
    remaining_seconds: int,
    option_blocks: list[list[str]],
    option_count: int,
    answer_buffer: str = "",
) -> None:
    lines = build_round_lines(score=score, remaining_seconds=remaining_seconds, option_blocks=option_blocks)

    clear_terminal()
    print("\n".join(lines))
    sys.stdout.write(f"Answer [1-{option_count}, q to quit] -> {answer_buffer}")
    sys.stdout.flush()


def update_round_timer(
    rendered_line_count: int,
    option_count: int,
    remaining_seconds: int,
    answer_buffer: str,
) -> None:
    if not sys.stdout.isatty():
        return

    up_lines = max(1, rendered_line_count - 2)
    prompt = f"Answer [1-{option_count}, q to quit] -> {answer_buffer}"
    sys.stdout.write(f"\033[{up_lines}A")
    sys.stdout.write("\r\033[2K")
    sys.stdout.write(f"Time left: {remaining_seconds:02d}s")
    sys.stdout.write(f"\033[{up_lines}B")
    sys.stdout.write("\r\033[2K")
    sys.stdout.write(prompt)
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
    render_callback: Callable[[int, str], None],
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
                choice, status = parse_choice(
                    input(f"Answer [1-{option_count}, q to quit] -> ").strip().lower(),
                    option_count,
                )
                return choice, status

            if not ready:
                continue

            char = sys.stdin.read(1)
            if char in ("\n", "\r"):
                print()
                choice, status = parse_choice(typed.strip().lower(), option_count)
                if status == "invalid":
                    typed = ""
                    last_remaining = -1
                    continue
                return choice, status

            if char in ("\x7f", "\b"):
                typed = typed[:-1]
                render_callback(remaining, typed)
                continue

            if char == "\x1b":
                while True:
                    try:
                        ready_more, _, _ = select.select([sys.stdin], [], [], 0.001)
                    except (OSError, ValueError):
                        break
                    if not ready_more:
                        break
                    _ = sys.stdin.read(1)
                continue

            lowered = char.lower()
            if lowered.isdigit() or lowered == "q":
                typed += lowered
                render_callback(remaining, typed)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)

