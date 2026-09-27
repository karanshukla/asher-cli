"""The command registry — the single source of truth for every TUI command."""

from __future__ import annotations

from .base import CommandRegistry
from .builtin import ClearCommand, HelpCommand, QuitCommand
from .lr5 import CameraAudioCommand, DrawerResetCommand, PrivacyCommand, VolumeCommand
from .robot import (
    CleanCommand,
    ExportCommand,
    HistoryCommand,
    InfoCommand,
    InsightCommand,
    LockCommand,
    NightLightBrightnessCommand,
    NightLightCommand,
    PanelBrightnessCommand,
    PowerCommand,
    RenameCommand,
    SleepCommand,
    SleepScheduleCommand,
    StatusCommand,
    UnlockCommand,
    WaitTimeCommand,
    WakeCommand,
)
from .slash import (
    CatCommand,
    ConfigCommand,
    LoginCommand,
    LogoutCommand,
    McpCommand,
    NotifyCommand,
    PetCommand,
    PetsCommand,
    RefreshCommand,
    RobotCommand,
    RobotsCommand,
    VersionCommand,
    WatchCommand,
)

_registry = CommandRegistry()
_registry.register(CleanCommand())
_registry.register(StatusCommand())
_registry.register(InfoCommand())
_registry.register(LockCommand())
_registry.register(UnlockCommand())
_registry.register(SleepCommand())
_registry.register(WakeCommand())
_registry.register(NightLightCommand())
_registry.register(NightLightBrightnessCommand())
_registry.register(PanelBrightnessCommand())
_registry.register(HistoryCommand())
_registry.register(WaitTimeCommand())
_registry.register(PowerCommand())
_registry.register(RenameCommand())
_registry.register(InsightCommand())
_registry.register(SleepScheduleCommand())
_registry.register(PrivacyCommand())
_registry.register(VolumeCommand())
_registry.register(CameraAudioCommand())
_registry.register(DrawerResetCommand())
_registry.register(ExportCommand())
_registry.register(HelpCommand())
_registry.register(ClearCommand())
_registry.register(QuitCommand())
_registry.register(LoginCommand())
_registry.register(LogoutCommand())
_registry.register(RobotsCommand())
_registry.register(RobotCommand())
_registry.register(PetsCommand())
_registry.register(PetCommand())
_registry.register(CatCommand())
_registry.register(RefreshCommand())
_registry.register(ConfigCommand())
_registry.register(NotifyCommand())
_registry.register(WatchCommand())
_registry.register(McpCommand())
_registry.register(VersionCommand())
