"""Slash commands — app management, never robot control."""

from __future__ import annotations

import asyncio
import contextlib
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app import AsherApp

from rich.text import Text
from textual.widgets import RichLog, Static

from ...core import theme
from ...core.helpers import (
    robot_model,
    ts,
)
from .base import HINT_SIGNIN, SlashCommand


def _persist(app: AsherApp, **changes: object) -> None:
    """Persist a runtime setting to ``~/.asher-cli/config.json``.

    A read-only filesystem (container, restricted environment) must not break
    the in-session command, so filesystem errors degrade to a warning log
    rather than raising.
    """
    from ...core.config import update  # noqa: PLC0415

    try:
        update(**changes)
    except OSError:
        app._log_warn("Could not save setting (filesystem read-only?)")


# ── slash commands ──────────────────────────────────────────────────────────


class LoginCommand(SlashCommand):
    name = "login"
    description = "sign in or switch accounts"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        app._start_login_flow()


class LogoutCommand(SlashCommand):
    name = "logout"
    description = "sign out and re-enter credentials"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        from ...core import credentials  # noqa: PLC0415

        if not app._account:
            app._log_warn("Not signed in.")
            return

        if app._robot:
            with contextlib.suppress(Exception):
                await app._robot.unsubscribe()
        with contextlib.suppress(Exception):
            await app._account.disconnect()
        app._account = None
        app._robot = None
        app._adapter = None
        credentials.delete()
        app._log_ok("Signed out.")
        app._log_info("Type /login to sign in.")
        app._set_cat("idle", "not signed in")
        app._show_signed_out_state()
        app.query_one("#hint-bar", Static).update(HINT_SIGNIN)


class RobotsCommand(SlashCommand):
    name = "robots"
    description = "list all robots on the account"

    async def run(self, app: AsherApp, args: list[str]) -> None:  # noqa: ARG002
        robots = app._robots
        if not robots:
            app._log_warn("No robots loaded - use /login to connect first.")
            return
        log = app.query_one("#log", RichLog)
        for idx, robot in enumerate(robots):
            active = robot is app._robot
            t = ts()
            t.append("  ● " if active else "    ", style=theme.OK if active else theme.MUTED)
            t.append(f"[{idx}] ", style=theme.MUTED)
            t.append(
                getattr(robot, "name", "-"),
                style=theme.FOREGROUND_BRIGHT if active else theme.FOREGROUND,
            )
            t.append(f"  {robot_model(robot)}", style=theme.MUTED)
            log.write(t)


class PetsCommand(SlashCommand):
    name = "pets"
    description = "list all pets on the account"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        pets = app._pets
        if not pets:
            app._log_warn("No pets found on this account.")
            return
        log = app.query_one("#log", RichLog)
        active_idx = getattr(app, "_active_pet_idx", 0)
        for idx, pet in enumerate(pets):
            active = idx == active_idx
            t = ts()
            t.append("  ● " if active else "    ", style=theme.OK if active else theme.MUTED)
            t.append(f"[{idx}] ", style=theme.MUTED)
            t.append(
                getattr(pet, "name", "-"),
                style=theme.FOREGROUND_BRIGHT if active else theme.FOREGROUND,
            )
            log.write(t)


class PetCommand(SlashCommand):
    name = "pet"
    description = "<index|name> switch active pet in status bar"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        pets = app._pets
        if not pets:
            app._log_warn("No pets found on this account.")
            return

        if not args:
            app._log_info("Usage: /pet <index|name>  - use /pets to list")
            return

        target = args[0]
        if target.isdigit():
            idx = int(target)
            if 0 <= idx < len(pets):
                app._active_pet_idx = idx
                _persist(app, active_pet_index=idx)
                name = getattr(pets[idx], "name", str(idx))
                app._log_ok(f"Showing pet: {name}")
                await app._refresh_status()
            else:
                app._log_warn(f"No pet at index {idx} - use /pet to list")
        else:
            tl = target.lower()
            match = next(
                (i for i, p in enumerate(pets) if tl in getattr(p, "name", "").lower()), None
            )
            if match is None:
                app._log_warn(f"No pet matching '{target}' - use /pet to list")
                return
            app._active_pet_idx = match
            _persist(app, active_pet_index=match)
            name = getattr(pets[match], "name", str(match))
            app._log_ok(f"Showing pet: {name}")
            await app._refresh_status()


class CatCommand(SlashCommand):
    name = "cat"
    description = "on|off|colour <hex>  configure the cat panel"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        if not args:
            app._log_info("Usage: /cat on|off|colour <hex>")
            return

        sub = args[0].lower()
        if sub == "off":
            app.query_one("#cat-panel").display = False
            app._cat_panel_visible = False
            _persist(app, cat_panel_visible=False)
            app._log_ok("Cat panel hidden")
        elif sub == "on":
            app.query_one("#cat-panel").display = True
            app._cat_panel_visible = True
            _persist(app, cat_panel_visible=True)
            app._log_ok("Cat panel visible")
        elif sub in ("colour", "color"):
            if len(args) < 2:
                app._log_warn(f"Usage: /cat colour <hex>  e.g. /cat colour {theme.PINK}")
                return
            color = args[1]
            if not color.startswith("#"):
                color = f"#{color}"
            app._cat_color = color
            _persist(app, cat_panel_color=color)
            app._set_cat(app._cat_mode, getattr(app, "_cat_label", ""))
            app._log_ok(f"Cat colour set to {color}")
        elif sub == "reset":
            app._cat_color = None
            _persist(app, cat_panel_color=None)
            app._set_cat(app._cat_mode, getattr(app, "_cat_label", ""))
            app._log_ok("Cat colour reset to default")
        else:
            app._log_warn("Usage: /cat on|off|colour <hex>")


class RefreshCommand(SlashCommand):
    name = "refresh"
    description = "<seconds|off>  change auto-refresh interval"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        poll_timer = getattr(app, "_poll_timer", None)

        if not args:
            interval = getattr(app, "_poll_interval", 300)
            if interval == 0:
                app._log_info("Auto-refresh is off")
            else:
                app._log_info(f"Auto-refresh interval: {interval}s")
            return

        raw = args[0].lower()
        if raw == "off":
            if poll_timer is not None:
                poll_timer.stop()
                app._poll_timer = None
            app._poll_interval = 0
            _persist(app, poll_interval_seconds=0)
            app._log_ok("Auto-refresh disabled")
            return

        try:
            seconds = max(10, int(raw))
        except ValueError:
            app._log_warn("Usage: /refresh <seconds|off>  (minimum 10s)")
            return

        if poll_timer is not None:
            poll_timer.stop()
        app._poll_timer = app.set_interval(seconds, app._poll_status_interval)
        app._poll_interval = seconds
        _persist(app, poll_interval_seconds=seconds)
        app._log_ok(f"Auto-refresh set to every {seconds}s")


def _watcher_summary() -> str:
    from ...desktop.daemon import running_pid  # noqa: PLC0415

    pid = running_pid()
    return f"running (pid {pid})" if pid is not None else "not running"


class ConfigCommand(SlashCommand):
    name = "config"
    description = "show current runtime configuration"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        log = app.query_one("#log", RichLog)

        robot = app._robot
        robot_name = getattr(robot, "name", "—") if robot else "not connected"
        robot_info = f"{robot_name} ({robot_model(robot)})" if robot else robot_name

        interval = getattr(app, "_poll_interval", 300)
        refresh_str = f"{interval}s" if interval else "off"

        cat_visible = getattr(app, "_cat_panel_visible", True)
        cat_color = getattr(app, "_cat_color", None) or f"{theme.ACCENT} (default)"

        pets = app._pets
        active_pet_idx = getattr(app, "_active_pet_idx", 0)
        if pets and active_pet_idx < len(pets):
            pet_str = f"{getattr(pets[active_pet_idx], 'name', '?')} (index {active_pet_idx})"
        elif pets:
            pet_str = f"{getattr(pets[0], 'name', '?')} (index 0)"
        else:
            pet_str = "none"

        rows = [
            ("robot", robot_info),
            ("refresh", refresh_str),
            ("cat panel", f"{'on' if cat_visible else 'off'}  {cat_color}"),
            ("active pet", pet_str),
            (
                "notifications",
                "on" if getattr(app, "_notifications_enabled", True) else "off",
            ),
            (
                "notif. sound",
                "on" if getattr(app, "_notification_sound", False) else "off",
            ),
            ("watcher", _watcher_summary()),
        ]
        log.write("")
        for k, v in rows:
            t = Text()
            t.append(f"  {k:<14}", style=theme.MUTED)
            t.append(v, style=theme.FOREGROUND)
            log.write(t)
        log.write("")


class NotifyCommand(SlashCommand):
    name = "notify"
    description = "on|off|sound on|off|test  desktop toast settings"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        if not args:
            toasts = "on" if getattr(app, "_notifications_enabled", True) else "off"
            sound = "on" if getattr(app, "_notification_sound", False) else "off"
            app._log_info(
                f"Usage: /notify on|off|sound on|off|test  (toasts {toasts}, sound {sound})"
            )
            return

        sub = args[0].lower()
        if sub == "on":
            app._notifications_enabled = True
            _persist(app, notifications=True)
            app._log_ok("Desktop notifications enabled")
        elif sub == "off":
            app._notifications_enabled = False
            _persist(app, notifications=False)
            app._log_ok("Desktop notifications disabled")
        elif sub == "sound":
            if len(args) < 2 or args[1].lower() not in ("on", "off"):
                app._log_warn("Usage: /notify sound on|off")
                return
            enabled = args[1].lower() == "on"
            app._notification_sound = enabled
            _persist(app, notification_sound=enabled)
            app._log_ok(f"Notification sound {'enabled' if enabled else 'disabled'}")
        elif sub == "test":
            if not getattr(app, "_notifications_enabled", True):
                app._log_warn("Notifications are off — /notify on first")
                return
            from ...desktop.notifications import fire  # noqa: PLC0415

            name = getattr(getattr(app, "_robot", None), "name", "robot") or "robot"
            fire(f"Asher — {name}", "This is a test notification.")
            app._log_ok("Test notification fired")
        else:
            app._log_warn("Usage: /notify on|off|sound on|off|test")


class WatchCommand(SlashCommand):
    name = "watch"
    description = (
        "start|stop|status|enable|disable  background notifier that outlives this terminal"
    )

    async def run(self, app: AsherApp, args: list[str]) -> None:
        from ...desktop.autostart import disable as disable_autostart  # noqa: PLC0415
        from ...desktop.daemon import (  # noqa: PLC0415
            ACTIONS,
            enable_autostart,
            start,
            status,
            stop,
        )

        action = args[0].lower() if args else "status"
        if action not in ACTIONS or action == "run":
            app._log_warn("Usage: /watch start|stop|status|enable|disable")
            return

        handlers = {
            "start": start,
            "stop": stop,
            "status": status,
            "enable": enable_autostart,
            "disable": disable_autostart,
        }
        # Each of these blocks on process signals and short sleeps, which would
        # otherwise stall the UI for the length of the daemon's shutdown grace.
        ok, message = await asyncio.to_thread(handlers[action])
        for line in message.splitlines():
            (app._log_ok if ok else app._log_warn)(line)
        if ok and action == "start":
            app._log_info("Dashboard toasts are suppressed while the watcher runs.")


class RobotCommand(SlashCommand):
    name = "robot"
    description = "<index|name> switch active robot"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        robots = app._robots
        if not robots:
            app._log_warn("No robots loaded - use /login to connect first.")
            return

        if not args:
            app._log_info("Usage: /robot <index|name>  - use /robots to list")
            return

        target = " ".join(args)
        robot = None
        if target.isdigit():
            idx = int(target)
            if 0 <= idx < len(robots):
                robot = robots[idx]
            else:
                app._log_warn(f"No robot at index {idx} - use /robots to list")
                return
        else:
            tl = target.lower()
            robot = next((rb for rb in robots if tl in getattr(rb, "name", "").lower()), None)
            if robot is None:
                app._log_warn(f"No robot matching '{target}' - use /robots to list")
                return

        if robot is app._robot:
            app._log_info(f"Already using '{getattr(robot, 'name', '?')}'")
            return

        if app._robot is not None:
            with contextlib.suppress(Exception):
                await app._robot.unsubscribe()

        app._robot = robot
        from ...robot.adapters import make_adapter  # noqa: PLC0415

        app._adapter = make_adapter(robot)
        await app._start_monitoring()  # type: ignore[attr-defined]
        await app._update_last_cat_seen()  # type: ignore[attr-defined]
        await app._refresh_status()  # type: ignore[attr-defined]

        name = getattr(robot, "name", "?")
        app._log_ok(f"Switched to '{name}' ({robot_model(robot)})")
        app._set_cat("happy", "connected!")  # type: ignore[attr-defined]

        serial = getattr(robot, "serial", None)
        if serial:
            from ...core import credentials  # noqa: PLC0415

            credentials.save_preferred_robot(serial)


async def _ensure_mcp_extra(app: AsherApp) -> bool:
    """Install pylitterbot's mcp extra if it isn't already available. Returns success."""
    from importlib.metadata import version as pkg_version  # noqa: PLC0415

    from ...mcp.config import mcp_extra_installed  # noqa: PLC0415

    if mcp_extra_installed():
        return True

    pin = f"pylitterbot[mcp]=={pkg_version('pylitterbot')}"
    app._log_info(f"Installing {pin}…")
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "pip",
        "install",
        pin,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output = (await proc.communicate())[0].decode(errors="replace")
    if proc.returncode == 0:
        app._log_ok("Installed pylitterbot[mcp].")
        return True

    app._log_err("Failed to install pylitterbot[mcp]:")
    for line in output.splitlines()[-10:]:
        app._log_err(f"  {line}")
    app._log_info(f"Try manually: {sys.executable} -m pip install '{pin}'")
    return False


class McpCommand(SlashCommand):
    name = "mcp"
    description = "on|off|status  Litter-Robot MCP server for Claude Desktop"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        from ...mcp.config import mcp_status, set_mcp_enabled  # noqa: PLC0415

        sub = args[0].lower() if args else "status"
        if sub not in ("on", "off", "status"):
            app._log_warn("Usage: /mcp on|off|status")
            return

        if sub == "status":
            from ...core import credentials  # noqa: PLC0415

            email, password = credentials.load()
            has_keyring_creds = bool(email and password)
            has_env_creds = all(credentials.from_env())
            if has_keyring_creds:
                app._log_info("Credentials: present in keyring")
            elif has_env_creds:
                app._log_info("Credentials: present in .env (will be copied to keyring on /mcp on)")
            else:
                app._log_info("Credentials: missing - use /login first")
            for path, enabled in mcp_status():
                state = "enabled " if enabled else "disabled"
                found = "found" if path.exists() else "not found"
                app._log_info(f"  [{state}, {found}]  {path}")
            return

        if sub == "on":
            from ...core import credentials  # noqa: PLC0415

            email, password = credentials.load()
            if not email or not password:
                env_email, env_password = credentials.from_env()
                if env_email and env_password and credentials.save(env_email, env_password):
                    app._log_info("Copied .env credentials into the OS keyring for MCP use.")
                    email, password = env_email, env_password

            if not email or not password:
                app._log_err("No credentials in the keyring - use /login first.")
                return
            if not await _ensure_mcp_extra(app):
                return
            touched = set_mcp_enabled(True)
        else:
            touched = set_mcp_enabled(False)

        verb = "enabled" if sub == "on" else "disabled"
        if touched:
            for path in touched:
                app._log_ok(f"MCP server '{verb}' in {path}")
            app._log_info("Restart Claude Desktop to apply this change.")
        else:
            app._log_info(f"MCP server was already {verb}")


class VersionCommand(SlashCommand):
    name = "version"
    description = "show version info (asher-cli, Python, pylitterbot, textual)"

    async def run(self, app: AsherApp, args: list[str]) -> None:  # noqa: ARG002
        def _v(pkg: str) -> str:
            try:
                return pkg_version(pkg)
            except PackageNotFoundError:
                return "?"

        app._log_info(f"Asher CLI v{_v('asher-cli')}")
        app._log_info(f"Python {sys.version.split()[0]}")
        app._log_info(f"pylitterbot {_v('pylitterbot')}")
        app._log_info(f"textual {_v('textual')}")

        from ...core.updates import check, releases_url  # noqa: PLC0415

        update = await asyncio.to_thread(check, force=True)
        if update is None:
            app._log_ok("You're on the latest release.")
        else:
            app._log_warn(update.notice)
            app._log_info(f"Changelog: {releases_url()}")
