"""Tests for the /mcp slash command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from asher.commands import McpCommand


async def _make_awaitable(value):
    return value


def _await_result(value):
    return _make_awaitable(value)


@pytest.fixture
def app():
    mock = MagicMock()
    mock._log_ok = MagicMock()
    mock._log_err = MagicMock()
    mock._log_warn = MagicMock()
    mock._log_info = MagicMock()
    return mock


@pytest.mark.asyncio
class TestMcpCommand:
    async def test_on_without_credentials_logs_error(self, app, monkeypatch):
        monkeypatch.delenv("LITTER_ROBOT_USER", raising=False)
        monkeypatch.delenv("LITTER_ROBOT_PASSWORD", raising=False)
        with patch("asher.connection._keyring_load", return_value=("", "")):
            await McpCommand().run(app, ["on"])
        app._log_err.assert_called_once()

    async def test_on_falls_back_to_env_and_copies_to_keyring(self, app, monkeypatch):
        monkeypatch.setenv("LITTER_ROBOT_USER", "env@example.com")
        monkeypatch.setenv("LITTER_ROBOT_PASSWORD", "envpw")
        with (
            patch("asher.connection._keyring_load", return_value=("", "")),
            patch("asher.connection._keyring_save", return_value=True) as mock_save,
            patch("asher.mcp_config.mcp_extra_installed", return_value=True),
            patch("asher.mcp_config.set_mcp_enabled", return_value=[Path("x")]),
        ):
            await McpCommand().run(app, ["on"])
        mock_save.assert_called_once_with("env@example.com", "envpw")
        app._log_ok.assert_called_once()

    async def test_on_with_credentials_enables_server(self, app):
        with (
            patch("asher.connection._keyring_load", return_value=("a@b.com", "pw")),
            patch("asher.mcp_config.mcp_extra_installed", return_value=True),
            patch("asher.mcp_config.set_mcp_enabled", return_value=[Path("x")]) as mock_set,
        ):
            await McpCommand().run(app, ["on"])
        mock_set.assert_called_once_with(True)
        app._log_ok.assert_called_once()

    async def test_on_installs_missing_mcp_extra_before_enabling(self, app):
        proc = MagicMock()
        proc.communicate = MagicMock(return_value=_await_result((b"installed\n", None)))
        proc.returncode = 0
        with (
            patch("asher.connection._keyring_load", return_value=("a@b.com", "pw")),
            patch("asher.mcp_config.mcp_extra_installed", return_value=False),
            patch("asyncio.create_subprocess_exec", return_value=proc),
            patch("asher.mcp_config.set_mcp_enabled", return_value=[Path("x")]) as mock_set,
        ):
            await McpCommand().run(app, ["on"])
        mock_set.assert_called_once_with(True)

    async def test_on_skips_enabling_when_install_fails(self, app):
        proc = MagicMock()
        proc.communicate = MagicMock(return_value=_await_result((b"boom\n", None)))
        proc.returncode = 1
        with (
            patch("asher.connection._keyring_load", return_value=("a@b.com", "pw")),
            patch("asher.mcp_config.mcp_extra_installed", return_value=False),
            patch("asyncio.create_subprocess_exec", return_value=proc),
            patch("asher.mcp_config.set_mcp_enabled") as mock_set,
        ):
            await McpCommand().run(app, ["on"])
        mock_set.assert_not_called()
        app._log_err.assert_called()

    async def test_off_disables_server(self, app):
        with patch("asher.mcp_config.set_mcp_enabled", return_value=[Path("x")]) as mock_set:
            await McpCommand().run(app, ["off"])
        mock_set.assert_called_once_with(False)
        app._log_ok.assert_called_once()

    async def test_off_when_already_disabled_logs_info_not_ok(self, app):
        with patch("asher.mcp_config.set_mcp_enabled", return_value=[]):
            await McpCommand().run(app, ["off"])
        app._log_ok.assert_not_called()
        app._log_info.assert_called_once()

    async def test_status_reports_state(self, app, monkeypatch):
        monkeypatch.delenv("LITTER_ROBOT_USER", raising=False)
        monkeypatch.delenv("LITTER_ROBOT_PASSWORD", raising=False)
        with (
            patch(
                "asher.mcp_config.mcp_status",
                return_value=[(Path("/x/claude_desktop_config.json"), True)],
            ),
            patch("asher.connection._keyring_load", return_value=("a@b.com", "pw")),
        ):
            await McpCommand().run(app, ["status"])
        assert app._log_info.call_count == 2

    async def test_bad_argument_warns_usage(self, app):
        await McpCommand().run(app, ["bogus"])
        app._log_warn.assert_called_once()
