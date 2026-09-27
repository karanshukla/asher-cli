"""Catppuccin Mocha palette — the single source of truth for every colour in the app.

Two layers:

* the **raw palette** — the 26 official Catppuccin Mocha swatches, named exactly
  as upstream does (https://catppuccin.com/palette) so they can be checked
  against the spec at a glance;
* the **semantic roles** — what Asher actually paints with (``BACKGROUND``,
  ``MUTED``, ``DANGER``, …). Widgets and Rich styles reference the roles, never
  the raw swatches, so re-flavouring the app (Latte, Frappé, Macchiato) means
  repointing the roles here and nothing else.

``CSS_VARIABLES`` exposes the same roles to ``ui/style.tcss`` (and the screen-level
``CSS`` blocks) as ``$asher-*`` variables via ``AsherApp.get_css_variables()``, so
the stylesheet and the Python-side styles can't drift apart.
"""

from __future__ import annotations

# ── Catppuccin Mocha, verbatim ───────────────────────────────────────────────
ROSEWATER = "#f5e0dc"
FLAMINGO = "#f2cdcd"
PINK = "#f5c2e7"
MAUVE = "#cba6f7"
RED = "#f38ba8"
MAROON = "#eba0ac"
PEACH = "#fab387"
YELLOW = "#f9e2af"
GREEN = "#a6e3a1"
TEAL = "#94e2d5"
SKY = "#89dceb"
SAPPHIRE = "#74c7ec"
BLUE = "#89b4fa"
LAVENDER = "#b4befe"
TEXT = "#cdd6f4"
SUBTEXT1 = "#bac2de"
SUBTEXT0 = "#a6adc8"
OVERLAY2 = "#9399b2"
OVERLAY1 = "#7f849c"
OVERLAY0 = "#6c7086"
SURFACE2 = "#585b70"
SURFACE1 = "#45475a"
SURFACE0 = "#313244"
BASE = "#1e1e2e"
MANTLE = "#181825"
CRUST = "#11111b"

# ── Semantic roles ───────────────────────────────────────────────────────────
BACKGROUND = BASE
"""App and log background."""

PANEL = MANTLE
"""Chrome that sits above the background: status bar, input bar, overlays."""

BORDER = SURFACE1
"""Visible dividers between panels."""

BORDER_SUBTLE = SURFACE0
"""Hairline rules — welcome separator, cat-panel edge."""

DIM = SURFACE1
"""Placeholder glyphs: em dashes, shimmer, "no value yet"."""

MUTED = OVERLAY0
"""Labels and secondary chrome — the least-important readable text."""

SUBTLE = SUBTEXT0
"""Supporting copy: descriptions, cat-panel badges, hints."""

FOREGROUND = SUBTEXT1
"""Body text."""

FOREGROUND_BRIGHT = TEXT
"""Emphasised values — robot names, echoed commands, the active row."""

ACCENT = BLUE
"""Asher's primary accent: the cat, headings, the cycling chip."""

OK = GREEN
"""Success: connected, ready, cycle complete, the prompt caret."""

WARN = YELLOW
"""Attention without failure: cat detected, panel locked, paused."""

DANGER = RED
"""Failure: offline, drawer full, faults."""

SELECTION_BG = BLUE
"""Background of the highlighted completion row."""

SELECTION_FG = BASE
"""Foreground on ``SELECTION_BG`` — inverted for contrast."""

GLYPH_ON_DARK = TEXT
"""Icon silhouette drawn against a dark desktop panel."""

GLYPH_ON_LIGHT = CRUST
"""Icon silhouette drawn against a light desktop panel."""

# ── Animation pulses ─────────────────────────────────────────────────────────
# Each cat mode shimmers between adjacent Catppuccin hues rather than
# lightening a single one, which keeps every frame an in-palette colour.
ACCENT_PULSE = [ACCENT, SAPPHIRE, SKY, SAPPHIRE]
OK_PULSE = [OK, TEAL, OK, TEAL]
SUBTLE_PULSE = [SUBTEXT0, SUBTEXT1, TEXT, SUBTEXT1]
DANGER_PULSE = [DANGER, MAROON, DANGER, MAROON]
WARN_PULSE = [WARN, PEACH, WARN, PEACH]


CSS_VARIABLES: dict[str, str] = {
    "asher-bg": BACKGROUND,
    "asher-panel": PANEL,
    "asher-border": BORDER,
    "asher-border-subtle": BORDER_SUBTLE,
    "asher-muted": MUTED,
    "asher-subtle": SUBTLE,
    "asher-fg": FOREGROUND,
    "asher-fg-bright": FOREGROUND_BRIGHT,
    "asher-accent": ACCENT,
    "asher-ok": OK,
    "asher-warn": WARN,
    "asher-danger": DANGER,
}


def apply(css: str) -> str:
    """Resolve ``$asher-*`` role variables in an inline CSS block.

    ``ui/style.tcss`` gets these variables from ``AsherApp.get_css_variables()``,
    but a ``Screen``/``Widget`` CSS block can be mounted by any host app (the test
    harnesses mount ``LoginScreen`` and ``HistoryScreen`` on bare apps). Baking the
    values in at class-definition time keeps those blocks self-contained while
    still reading them from one place.
    """
    # Longest name first so ``$asher-border-subtle`` isn't clipped by ``$asher-border``.
    for name in sorted(CSS_VARIABLES, key=len, reverse=True):
        css = css.replace(f"${name}", CSS_VARIABLES[name])
    return css
