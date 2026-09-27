"""LR5-only robot commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app import AsherApp


from .base import Command

# ── LR5-only commands ─────────────────────────────────────────────────────────
# These route through the adapter, which returns a "not supported" message on
# LR3/LR4 rather than crashing — so the commands are safe to type on any model.


class PrivacyCommand(Command):
    name = "privacy"
    description = "on|off  toggle LR5 privacy mode"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "privacy on|off"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        if app._adapter is None:
            return
        arg = args[0].lower() if args else ""
        if arg not in ("on", "off"):
            app._log_warn("Usage: privacy on|off")
            return
        ok, msg = await app._adapter.set_privacy_mode(arg == "on")
        if ok:
            app._log_ok(msg)
            await app._refresh_status()
        else:
            app._log_warn(msg)


class VolumeCommand(Command):
    name = "volume"
    description = "<0-100>  set LR5 sound volume"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "volume <0-100>"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        if app._adapter is None:
            return
        if not args or not args[0].lstrip("-").isdigit():
            current = getattr(app._robot, "sound_volume", None)
            extra = f"  (current: {current})" if current is not None else ""
            app._log_warn(f"Usage: volume <0-100>{extra}")
            return
        ok, msg = await app._adapter.set_volume(int(args[0]))
        if ok:
            app._log_ok(msg)
            await app._refresh_status()
        else:
            app._log_warn(msg)


class CameraAudioCommand(Command):
    name = "camera-audio"
    aliases = ("cameraaudio",)
    description = "on|off  toggle LR5 camera audio"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "camera-audio on|off"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        if app._adapter is None:
            return
        arg = args[0].lower() if args else ""
        if arg not in ("on", "off"):
            app._log_warn("Usage: camera-audio on|off")
            return
        ok, msg = await app._adapter.set_camera_audio(arg == "on")
        if ok:
            app._log_ok(msg)
            await app._refresh_status()
        else:
            app._log_warn(msg)


class DrawerResetCommand(Command):
    name = "drawer-reset"
    aliases = ("drawerreset",)
    description = "reset the LR5 waste drawer level indicator"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "drawer-reset"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        if app._adapter is None:
            return
        ok, msg = await app._adapter.reset_waste_drawer()
        if ok:
            app._log_ok(msg)
            await app._refresh_status()
        else:
            app._log_warn(msg)
