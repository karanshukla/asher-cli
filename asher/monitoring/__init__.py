"""Robot status monitoring — WebSocket primary, polling fallback."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pylitterbot.enums import LitterBoxStatus
from rich.text import Text
from textual import work
from textual.widgets import Static

from ..helpers import drawer_bar, fmt_ago, robot_model

if TYPE_CHECKING:
    from ..robot_protocol import RobotProtocol


class MonitoringMixin:
    # declared for type checkers; assigned in AsherApp.__init__
    _robot: RobotProtocol | None
    _pets: list
    _cat_mode: str
    _last_cat_seen: datetime | None

    async def _start_monitoring(self) -> None:
        """Subscribe to WebSocket push updates from the robot."""
        from pylitterbot.robot import EVENT_UPDATE  # noqa: PLC0415

        if self._robot is None:
            return
        try:
            self._robot.on(EVENT_UPDATE, self._on_robot_update)
            await self._robot.subscribe()
        except Exception:
            pass

    def _on_robot_update(self) -> None:
        """Sync callback fired by pylitterbot when robot state changes via WebSocket."""
        self._handle_ws_update()  # type: ignore[attr-defined]

    @work(exclusive=True)
    async def _handle_ws_update(self) -> None:
        if self._robot is None:
            return
        await self._refresh_status()

    async def _update_last_cat_seen(self) -> None:
        """Cache the timestamp of the most recent cat-detection event from activity history."""
        if self._robot is None:
            return
        try:
            acts = await self._robot.get_activity_history(limit=50)
            for act in acts:
                if getattr(act, "action", None) == LitterBoxStatus.CAT_DETECTED:
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
        last_seen = self._last_cat_seen or getattr(r, "last_seen", None)

        weight_val = "—"
        try:
            w = getattr(r, "pet_weight", None)
            if w is not None and float(w) > 0:
                weight_val = f"{float(w):.1f} lb"
        except Exception:
            pass

        pet_name = self._pets[0].name if self._pets else None

        robot_txt = Text(name, style="bold #e6edf3")
        robot_txt.append(f"  {robot_model(r)}", style="#484f58")
        self.query_one("#robot-lbl", Static).update(robot_txt)  # type: ignore[attr-defined]

        robot_status = getattr(r, "status", None)
        online_lbl = self.query_one("#online-lbl", Static)  # type: ignore[attr-defined]
        if not online:
            online_lbl.update(Text("○ OFFLINE", style="bold #f85149"))
        elif robot_status is LitterBoxStatus.CAT_DETECTED:
            online_lbl.update(Text("~ Cat inside", style="bold #3fb950"))
        elif robot_status is LitterBoxStatus.CAT_SENSOR_TIMING:
            online_lbl.update(Text("⏱ Cat delay", style="bold #d29922"))
        elif robot_status in (LitterBoxStatus.CLEAN_CYCLE, LitterBoxStatus.EMPTY_CYCLE):
            online_lbl.update(Text("⟳ Cycling", style="bold #58a6ff"))
        elif robot_status is LitterBoxStatus.PAUSED:
            online_lbl.update(Text("⏸ Paused", style="bold #d29922"))
        elif robot_status is LitterBoxStatus.CLEAN_CYCLE_COMPLETE:
            online_lbl.update(Text("✓ Cycle done", style="bold #3fb950"))
        elif robot_status in (
            LitterBoxStatus.DRAWER_FULL,
            LitterBoxStatus.DRAWER_FULL_1,
            LitterBoxStatus.DRAWER_FULL_2,
        ):
            online_lbl.update(Text("⚠ Drawer full", style="bold #f85149"))
        else:
            online_lbl.update(Text("● ONLINE", style="bold #3fb950"))

        nl_mode = getattr(r, "night_light_mode", None)
        nl_enabled = getattr(r, "night_light_mode_enabled", False)
        nl_brightness = getattr(r, "night_light_brightness", None)

        mode_str = nl_mode.value.lower() if nl_mode is not None else ("on" if nl_enabled else "off")
        if mode_str == "off":
            nl_emoji, nl_color = "○", "#484f58"
        elif mode_str == "auto":
            nl_emoji, nl_color = "◐", "#58a6ff"
        else:
            nl_emoji, nl_color = "☀", "#d29922"

        nl = Text()
        nl.append(nl_emoji, style=nl_color)
        if nl_brightness and mode_str != "off":
            nl.append(f"  {nl_brightness}%", style="#484f58")
        self.query_one("#nightlight-lbl", Static).update(nl)  # type: ignore[attr-defined]

        panel_locked = getattr(r, "panel_lock_enabled", False)
        lock_text = Text()
        if panel_locked:
            lock_text.append("⊘ Locked", style="bold #d29922")
        else:
            lock_text.append("□ Unlocked", style="#484f58")
        self.query_one("#lock-lbl", Static).update(lock_text)  # type: ignore[attr-defined]

        bar = drawer_bar(drawer)
        dt = Text()
        dt.append("Drawer ", style="#484f58")
        dt.append_text(bar)
        dt.append(f" {drawer:.0f}%", style="#8b949e")
        self.query_one("#drawer-lbl", Static).update(dt)  # type: ignore[attr-defined]

        litter_raw = getattr(r, "litter_level", None)
        lt = Text()
        lt.append("Litter ", style="#484f58")
        if litter_raw is not None:
            lt.append(f"{float(litter_raw):.0f}%", style="#8b949e")
        else:
            lt.append("—", style="#30363d")
        self.query_one("#litter-lbl", Static).update(lt)  # type: ignore[attr-defined]

        visit_label = "Last visit" if self._last_cat_seen else "Last seen"
        self.query_one("#clean-lbl", Static).update(  # type: ignore[attr-defined]
            Text(f"{visit_label} {fmt_ago(last_seen)}", style="#484f58")
        )

        wt_text = Text()
        if pet_name:
            wt_text.append(pet_name, style="#8b949e")
            wt_text.append(" / ", style="#484f58")
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
