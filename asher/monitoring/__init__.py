"""Robot status monitoring — WebSocket primary, polling fallback."""

from __future__ import annotations

import contextlib
from datetime import datetime
from typing import TYPE_CHECKING

from pylitterbot.enums import LitterBoxStatus
from rich.text import Text
from textual import work
from textual.css.query import NoMatches
from textual.widgets import Static

from ..constants import STATUS_COLORS
from ..faults import SEVERITY_ERROR, check_faults
from ..helpers import drawer_bar, fmt_ago, robot_model

if TYPE_CHECKING:
    from textual.timer import Timer

    from ..robot_protocol import RobotProtocol


_CYCLING_STATUSES = frozenset({LitterBoxStatus.CLEAN_CYCLE, LitterBoxStatus.EMPTY_CYCLE})


class MonitoringMixin:
    # declared for type checkers; assigned in AsherApp.__init__
    _robot: RobotProtocol | None
    _pets: list
    _cat_mode: str
    _last_cat_seen: datetime | None
    _prev_faults: set[str]
    _fault_dismissed: set[str]
    _cycle_start: datetime | None
    _cycle_timer: Timer | None

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

        active_pet_idx = getattr(self, "_active_pet_idx", 0)
        pet = (
            self._pets[active_pet_idx]
            if self._pets and active_pet_idx < len(self._pets)
            else (self._pets[0] if self._pets else None)
        )
        pet_name = pet.name if pet else None

        robot_txt = Text(name, style="bold #e6edf3")
        robot_txt.append(f"  {robot_model(r)}", style="#484f58")
        self.query_one("#robot-lbl", Static).update(robot_txt)  # type: ignore[attr-defined]

        robot_status = getattr(r, "status", None)
        online_lbl = self.query_one("#online-lbl", Static)  # type: ignore[attr-defined]
        if not online:
            online_lbl.update(Text("○ OFFLINE", style="bold #f85149"))
            self._stop_cycle_timer()
        elif robot_status is LitterBoxStatus.CAT_DETECTED:
            online_lbl.update(Text("~ Cat inside", style="bold #3fb950"))
            self._stop_cycle_timer()
        elif robot_status is LitterBoxStatus.CAT_SENSOR_TIMING:
            online_lbl.update(Text("⏱ Cat delay", style="bold #d29922"))
            self._stop_cycle_timer()
        elif robot_status in _CYCLING_STATUSES:
            self._start_cycle_timer()
            online_lbl.update(self._cycling_chip())
        elif robot_status is LitterBoxStatus.PAUSED:
            online_lbl.update(Text("⏸ Paused", style="bold #d29922"))
            self._stop_cycle_timer()
        elif robot_status is LitterBoxStatus.CLEAN_CYCLE_COMPLETE:
            online_lbl.update(Text("✓ Cycle done", style="bold #3fb950"))
            self._stop_cycle_timer()
        elif robot_status in (
            LitterBoxStatus.DRAWER_FULL,
            LitterBoxStatus.DRAWER_FULL_1,
            LitterBoxStatus.DRAWER_FULL_2,
        ):
            online_lbl.update(Text("⚠ Drawer full", style="bold #f85149"))
            self._stop_cycle_timer()
        else:
            online_lbl.update(Text("● ONLINE", style="bold #3fb950"))
            self._stop_cycle_timer()

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

        self._update_cat_panel(r)
        faults_active = self._refresh_faults(r)

        if faults_active:
            if self._cat_mode != "error":
                self._set_cat("error", "fault!")  # type: ignore[attr-defined]
        elif drawer >= 85 and self._cat_mode not in ("cleaning", "error"):
            self._set_cat("full", "drawer full!")  # type: ignore[attr-defined]
        elif self._cat_mode == "error":
            self._set_cat("idle", "ready")  # type: ignore[attr-defined]

    def _update_cat_panel(self, r: RobotProtocol) -> None:
        """Render the cat-panel status badges: status chip, lock, light, sleep, wait."""
        status = getattr(r, "status", None)
        locked = bool(getattr(r, "panel_lock_enabled", False))
        sleeping = bool(getattr(r, "sleep_mode_enabled", False))
        night = bool(getattr(r, "night_light_mode_enabled", False))
        wait = getattr(r, "clean_cycle_wait_time_minutes", None)

        status_str = status.value if status is not None and hasattr(status, "value") else "—"
        status_color = STATUS_COLORS.get(status_str, "#8b949e")

        t = Text()
        t.append(f"● {status_str}\n", style=status_color)
        t.append("🔒 locked\n" if locked else "🔓 unlocked\n", style="#8b949e")
        t.append("💤 sleeping\n" if sleeping else "😺 awake\n", style="#8b949e")
        t.append("☀ light on\n" if night else "☾ light off\n", style="#8b949e")
        if wait:
            t.append(f"⏱ wait {wait}m\n", style="#484f58")
        self.query_one("#cat-status", Static).update(t)  # type: ignore[attr-defined]

    def _refresh_faults(self, r: RobotProtocol) -> bool:
        """Render the fault banner and log transitions. Returns True if any fault active."""
        faults = check_faults(r)
        active_labels = {f.label for f in faults}

        for label in active_labels - self._prev_faults:
            self._log_err(f"FAULT: {label}")  # type: ignore[attr-defined]
        for label in self._prev_faults - active_labels:
            self._log_ok(f"Cleared: {label}")  # type: ignore[attr-defined]

        self._prev_faults = active_labels
        if active_labels != self._fault_dismissed:
            self._fault_dismissed = set()

        try:
            banner = self.query_one("#fault-banner", Static)  # type: ignore[attr-defined]
        except NoMatches:
            return bool(faults)

        if not faults:
            banner.display = False
            banner.update(Text(""))
            return False

        t = Text()
        for i, f in enumerate(faults):
            if i:
                t.append("\n")
            prefix = "✖ " if f.severity == SEVERITY_ERROR else "⚠ "
            color = "#f85149" if f.severity == SEVERITY_ERROR else "#d29922"
            t.append(f"{prefix}{f.label}", style=color)
        banner.update(t)
        banner.display = self._fault_dismissed != active_labels
        return True

    def _cycling_chip(self) -> Text:
        """Build the `⟳ Cycling M:SS` chip using `_cycle_start`."""
        base = "⟳ Cycling"
        if self._cycle_start is None:
            return Text(base, style="bold #58a6ff")
        elapsed = int((datetime.now() - self._cycle_start).total_seconds())
        mm, ss = divmod(elapsed, 60)
        return Text(f"{base}  {mm}:{ss:02d}", style="bold #58a6ff")

    def _start_cycle_timer(self) -> None:
        """Begin tracking an active clean cycle (idempotent)."""
        if self._cycle_start is None:
            self._cycle_start = datetime.now()
        if self._cycle_timer is None:
            self._cycle_timer = self.set_interval(1, self._tick_cycle)  # type: ignore[attr-defined]

    def _stop_cycle_timer(self) -> None:
        """Stop tracking a cycle and clear the elapsed-time chip."""
        self._cycle_start = None
        if self._cycle_timer is not None:
            self._cycle_timer.stop()
            self._cycle_timer = None

    def _tick_cycle(self) -> None:
        """Per-second refresh of the cycling chip while a cycle is active."""
        if self._cycle_start is None or self._robot is None:
            return
        with contextlib.suppress(NoMatches):
            self.query_one("#online-lbl", Static).update(self._cycling_chip())  # type: ignore[attr-defined]

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
