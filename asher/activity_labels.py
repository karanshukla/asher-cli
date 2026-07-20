"""Pure helpers for translating raw pylitterbot activity strings into readable labels.

No Textual or pylitterbot runtime imports — only data and a pure function, so it
trivially unit-tests without an event loop or widget tree. Shared by the
``history`` command and the CSV ``export`` path so both render events the same way.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pylitterbot.activity import Activity

# Raw lowercased activity text → (human-readable label, colour).
# Colours match the GitHub-dark palette used elsewhere in the TUI.
ACTION_LABELS: dict[str, tuple[str, str]] = {
    "ready": ("Ready", "#484f58"),
    "litter robot is ready.": ("Ready", "#484f58"),
    "clean cycle complete": ("Clean cycle complete", "#3fb950"),
    "clean cycle in progress": ("Cleaning…", "#58a6ff"),
    "cat detected": ("Cat detected", "#d29922"),
    "cat sensor interrupted": ("Cat sensor tripped", "#d29922"),
    "drawer full": ("Drawer full — empty now", "#f85149"),
    "drawer full cleared": ("Drawer emptied", "#3fb950"),
    "sleep mode on": ("Sleep mode on", "#484f58"),
    "sleep mode off": ("Sleep mode off", "#484f58"),
    "panel locked": ("Panel locked", "#484f58"),
    "panel unlocked": ("Panel unlocked", "#484f58"),
    "offline": ("Offline", "#f85149"),
    "power off": ("Powered off", "#f85149"),
    "power on": ("Powered on", "#3fb950"),
    "motor fault": ("Motor fault", "#f85149"),
    "pinch detect": ("Pinch detected", "#f85149"),
    "timing fault": ("Timing fault", "#d29922"),
}

# Fallback colour for unknown event types — muted grey rather than crashing.
UNKNOWN_COLOUR = "#8b949e"


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
