"""Robot status polling and refresh."""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual import work
from textual.widgets import Static

from ..helpers import drawer_bar, fmt_ago


class MonitoringMixin:
    # declared for type checkers; assigned in AsherApp.__init__
    _robot: Any
    _pets: list
    _cat_mode: str
    _last_cat_seen: Any

    async def _update_last_cat_seen(self) -> None:
        """Cache the timestamp of the most recent cat-detection event from activity history."""
        if self._robot is None:
            return
        try:
            acts = await self._robot.get_activity_history(limit=10)
            for act in acts:
                w = getattr(act, "weight", None)
                action = getattr(act, "action", None)
                action_text = (action.text if hasattr(action, "text") else str(action)).lower()
                if (w is not None and float(w) > 0) or "cat" in action_text:
                    ts_dt = getattr(act, "timestamp", None)
                    if ts_dt is not None:
                        self._last_cat_seen = ts_dt
                        return
        except Exception:
            pass

    async def _refresh_status(self) -> None:
        r = self._robot
        if r is None:
            return
        self._is_loading = False

        name = getattr(r, "name", "—")
        online = getattr(r, "is_online", False)
        drawer = float(getattr(r, "waste_drawer_level", 0) or 0)
        status = getattr(r, "status", None)
        sleeping = getattr(r, "sleeping", False)
        last_seen = self._last_cat_seen or getattr(r, "last_seen", None)

        status_str = status.value if status else ("Sleeping" if sleeping else "Ready")

        weight_val = "—"
        try:
            w = getattr(r, "pet_weight", None)
            if w is not None and float(w) > 0:
                weight_val = f"{float(w):.1f} lb"
        except Exception:
            pass

        pet_name = self._pets[0].name if self._pets else None

        self.query_one("#robot-lbl", Static).update(Text(name, style="bold #e6edf3"))  # type: ignore[attr-defined]

        online_lbl = self.query_one("#online-lbl", Static)  # type: ignore[attr-defined]
        if online:
            online_lbl.update(Text("● ONLINE", style="bold #3fb950"))
        else:
            online_lbl.update(Text("○ OFFLINE", style="bold #f85149"))

        self.query_one("#status-lbl", Static).update(  # type: ignore[attr-defined]
            Text(f"[{status_str}]", style="#8b949e")
        )

        bar = drawer_bar(drawer)
        dt = Text()
        dt.append("Drawer ", style="#484f58")
        dt.append_text(bar)
        dt.append(f" {drawer:.0f}%", style="#8b949e")
        self.query_one("#drawer-lbl", Static).update(dt)  # type: ignore[attr-defined]

        visit_label = "Last visit" if self._last_cat_seen else "Last seen"
        self.query_one("#clean-lbl", Static).update(  # type: ignore[attr-defined]
            Text(f"{visit_label} {fmt_ago(last_seen)}", style="#484f58")
        )

        wt_text = Text()
        if pet_name:
            wt_text.append(pet_name, style="#8b949e")
            wt_text.append(" 🐱 ", style="#484f58")
        else:
            wt_text.append("cat ", style="#484f58")
        wt_text.append(weight_val, style="#8b949e")
        self.query_one("#weight-lbl", Static).update(wt_text)  # type: ignore[attr-defined]

        if drawer >= 85 and self._cat_mode not in ("cleaning", "error"):
            self._set_cat("full", "drawer full!")  # type: ignore[attr-defined]

    @work(exclusive=True)
    async def _poll_status_interval(self) -> None:
        if self._robot is None:
            return
        try:
            await self._robot.refresh()
            await self._update_last_cat_seen()
            await self._refresh_status()
        except Exception:
            pass
