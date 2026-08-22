"""Pure helpers for translating raw pylitterbot activity strings into readable labels.

No Textual or pylitterbot runtime imports — only data and a pure function, so it
trivially unit-tests without an event loop or widget tree. Shared by the
``history`` command and the CSV ``export`` path so both render events the same way.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from . import theme

if TYPE_CHECKING:
    from pylitterbot.activity import Activity

# Raw lowercased activity text → (human-readable label, colour).
# Colours are theme roles, so the palette stays consistent with the rest of the TUI.
ACTION_LABELS: dict[str, tuple[str, str]] = {
    "ready": ("Ready", theme.MUTED),
    "litter robot is ready.": ("Ready", theme.MUTED),
    "clean cycle complete": ("Clean cycle complete", theme.OK),
    "clean cycle in progress": ("Cleaning…", theme.ACCENT),
    "cat detected": ("Cat detected", theme.WARN),
    "cat sensor interrupted": ("Cat sensor tripped", theme.WARN),
    "drawer full": ("Drawer full — empty now", theme.DANGER),
    "drawer full cleared": ("Drawer emptied", theme.OK),
    "sleep mode on": ("Sleep mode on", theme.MUTED),
    "sleep mode off": ("Sleep mode off", theme.MUTED),
    "panel locked": ("Panel locked", theme.MUTED),
    "panel unlocked": ("Panel unlocked", theme.MUTED),
    "offline": ("Offline", theme.DANGER),
    "power off": ("Powered off", theme.DANGER),
    "power on": ("Powered on", theme.OK),
    "motor fault": ("Motor fault", theme.DANGER),
    "pinch detect": ("Pinch detected", theme.DANGER),
    "timing fault": ("Timing fault", theme.WARN),
    # The LR5 activity endpoint reports SCREAMING_SNAKE type codes rather than
    # the sentence-style text the LR3/LR4 history returns.
    "pet_visit": ("Cat visit", theme.WARN),
    "cat_detect": ("Cat detected", theme.WARN),
    "cycle_completed": ("Clean cycle complete", theme.OK),
    "cycle_interrupted": ("Cycle interrupted", theme.WARN),
    "litter_low": ("Litter low", theme.WARN),
}

# Fallback colour for unknown event types — muted grey rather than crashing.
UNKNOWN_COLOUR = theme.SUBTLE


def activity_raw_text(act: Activity) -> str:
    """Return the raw, stripped action text of an activity, regardless of type.

    ``Activity.action`` is ``str | LitterBoxStatus``; ``LitterBoxStatus`` exposes
    a ``.text`` property while plain strings are used as-is.
    """
    action: Any = getattr(act, "action", None)
    raw = action.text if hasattr(action, "text") else str(action)
    return raw.strip()


def format_activity(act: Activity, pets: list[Any] | None = None) -> tuple[str, str]:
    """Translate a single activity into a ``(display_label, colour)`` pair.

    Cat-detection events gain a weight and pet-name suffix when the data is
    available (``"Cat detected  Asher  9.1 lb"``). Unknown event types fall
    through to their raw string in muted grey — new pylitterbot events should
    never break the display.
    """
    raw_str = activity_raw_text(act)
    label, colour = ACTION_LABELS.get(raw_str.lower(), (raw_str, UNKNOWN_COLOUR))

    if "cat" in raw_str.lower():
        weight = getattr(act, "weight", None)
        pet_id = getattr(act, "pet_id", None)
        pet_name = None
        if pets and pet_id is not None:
            pet_name = next(
                (getattr(p, "name", None) for p in pets if getattr(p, "id", None) == pet_id),
                None,
            )
        if weight is not None:
            try:
                weight_str = f"{float(weight):.1f} lb"
            except (TypeError, ValueError):
                weight_str = ""
            if pet_name:
                label = f"{label}  {pet_name}  {weight_str}".rstrip()
            elif weight_str:
                label = f"{label}  {weight_str}"

    return label, colour
