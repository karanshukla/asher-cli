"""ASCII cat art definitions."""

from __future__ import annotations


def _frame(eyes: str, extra: str = "") -> str:
    """Build a single cat frame with the given eye expression and tail extra."""
    e1, e2 = eyes[0], eyes[2]
    line3 = "  \\" + e1 + " " + e2 + "/"
    last = "\\_____/" + extra
    return "\n".join([
        " /\\___/\\",
        " \\/   \\/",
        line3,
        " ==`^ ==",
        "  /   \\",
        " /|   |",
        " || - |",
        " ||   |",
        " ||| ||_",
        "/\\||_|//",
        last,
    ])


# idle: slow blink cycle (6 frames)
IDLE = [
    _frame("o o"),      # 0 eyes open
    _frame("o o"),      # 1
    _frame("- -"),      # 2 closing
    _frame("- -"),      # 3 closed
    _frame("o o"),      # 4 opening
    _frame("o o"),      # 5
]

# happy: purring tail vibration (6 frames)
HAPPY = [
    _frame("^ ^"),      # 0
    _frame("^ ^", "~"), # 1 purr
    _frame("^ ^"),      # 2
    _frame("^ ^", "~"), # 3 purr
    _frame("^ ^"),      # 4
    _frame("^ ^", "~"), # 5 purr
]

# sleeping: floating zZ (8 frames)
SLEEPING = [
    _frame("- -", " z"),  # 0
    _frame("- -", "zZ"),  # 1
    _frame("- -", " Z"),  # 2
    _frame("- -", "zZ"),  # 3
    _frame("- -", " z"),  # 4
    _frame("- -", "zZ"),  # 5
    _frame("- -", " Z"),  # 6
    _frame("- -", "zZ"),  # 7
]

# cleaning: active cycle (6 frames)
CLEANING = [
    _frame("@ o"),      # 0
    _frame("o @"),      # 1
    _frame("* *"),      # 2
    _frame("@ o"),      # 3
    _frame("o @"),      # 4
    _frame("* *"),      # 5
]

# error: alarm flash (4 frames)
ERROR = [
    _frame("x x"),      # 0
    _frame("x x", "!"), # 1 flash
    _frame("x x"),      # 2
    _frame("x x", "!"), # 3 flash
]

# full: agitated vibration (4 frames)
FULL = [
    _frame("! !"),      # 0
    _frame("! !", "~"), # 1 wiggle
    _frame("! !"),      # 2
    _frame("! !", "~"), # 3 wiggle
]

CATS: dict[str, list[str]] = {
    "idle": IDLE,
    "happy": HAPPY,
    "sleeping": SLEEPING,
    "cleaning": CLEANING,
    "error": ERROR,
    "full": FULL,
}
