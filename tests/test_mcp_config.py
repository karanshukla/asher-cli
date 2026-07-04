"""Tests for asher.mcp_config module."""

from __future__ import annotations

import json
from unittest.mock import patch

from asher.mcp_config import _SERVER_NAME, config_paths, mcp_status, set_mcp_enabled


class TestSetMcpEnabled:
    def test_enables_server_in_fresh_config(self, tmp_path):
        path = tmp_path / "claude_desktop_config.json"
        with patch("asher.mcp_config.config_paths", return_value=[path]):
            touched = set_mcp_enabled(True)
        assert touched == [path]
        data = json.loads(path.read_text(encoding="utf-8"))
        entry = data["mcpServers"][_SERVER_NAME]
        assert entry["args"] == ["-m", "asher.mcp_bridge"]

    def test_preserves_other_servers_on_enable(self, tmp_path):
        path = tmp_path / "claude_desktop_config.json"
        path.write_text(json.dumps({"mcpServers": {"other": {"command": "foo"}}}), encoding="utf-8")
        with patch("asher.mcp_config.config_paths", return_value=[path]):
            set_mcp_enabled(True)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "other" in data["mcpServers"]
        assert _SERVER_NAME in data["mcpServers"]

    def test_disables_existing_server(self, tmp_path):
        path = tmp_path / "claude_desktop_config.json"
        path.write_text(
            json.dumps({"mcpServers": {_SERVER_NAME: {"command": "x"}}}), encoding="utf-8"
        )
        with patch("asher.mcp_config.config_paths", return_value=[path]):
            touched = set_mcp_enabled(False)
        assert touched == [path]
        data = json.loads(path.read_text(encoding="utf-8"))
        assert _SERVER_NAME not in data["mcpServers"]

    def test_disable_when_not_enabled_is_a_noop(self, tmp_path):
        path = tmp_path / "claude_desktop_config.json"
        with patch("asher.mcp_config.config_paths", return_value=[path]):
            touched = set_mcp_enabled(False)
        assert touched == []
        assert not path.exists()

    def test_handles_corrupt_config_file(self, tmp_path):
        path = tmp_path / "claude_desktop_config.json"
        path.write_text("{not valid json", encoding="utf-8")
        with patch("asher.mcp_config.config_paths", return_value=[path]):
            set_mcp_enabled(True)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert _SERVER_NAME in data["mcpServers"]

    def test_enables_across_multiple_locations(self, tmp_path):
        standard = tmp_path / "standard" / "claude_desktop_config.json"
        msix = tmp_path / "msix" / "claude_desktop_config.json"
        with patch("asher.mcp_config.config_paths", return_value=[standard, msix]):
            touched = set_mcp_enabled(True)
        assert touched == [standard, msix]
        for path in (standard, msix):
            data = json.loads(path.read_text(encoding="utf-8"))
            assert _SERVER_NAME in data["mcpServers"]


class TestMcpStatus:
    def test_reports_disabled_when_no_config(self, tmp_path):
        path = tmp_path / "claude_desktop_config.json"
        with patch("asher.mcp_config.config_paths", return_value=[path]):
            result = mcp_status()
        assert result == [(path, False)]

    def test_reports_enabled_when_entry_present(self, tmp_path):
        path = tmp_path / "claude_desktop_config.json"
        path.write_text(
            json.dumps({"mcpServers": {_SERVER_NAME: {"command": "x"}}}), encoding="utf-8"
        )
        with patch("asher.mcp_config.config_paths", return_value=[path]):
            result = mcp_status()
        assert result == [(path, True)]


class TestConfigPaths:
    def test_windows_includes_msix_package_when_present(self, tmp_path, monkeypatch):
        monkeypatch.setattr("asher.mcp_config.sys.platform", "win32")
        appdata = tmp_path / "Roaming"
        local_appdata = tmp_path / "Local"
        packages_dir = local_appdata / "Packages" / "Claude_abc123"
        packages_dir.mkdir(parents=True)
        monkeypatch.setenv("APPDATA", str(appdata))
        monkeypatch.setenv("LOCALAPPDATA", str(local_appdata))

        paths = config_paths()

        assert appdata / "Claude" / "claude_desktop_config.json" in paths
        assert (
            packages_dir / "LocalCache" / "Roaming" / "Claude" / "claude_desktop_config.json"
            in paths
        )

    def test_windows_skips_msix_when_no_packages_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("asher.mcp_config.sys.platform", "win32")
        appdata = tmp_path / "Roaming"
        local_appdata = tmp_path / "Local"
        monkeypatch.setenv("APPDATA", str(appdata))
        monkeypatch.setenv("LOCALAPPDATA", str(local_appdata))

        paths = config_paths()

        assert paths == [appdata / "Claude" / "claude_desktop_config.json"]

    def test_linux_includes_alt_dir_when_present(self, tmp_path, monkeypatch):
        monkeypatch.setattr("asher.mcp_config.sys.platform", "linux")
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        alt_dir = tmp_path / ".config" / "claude-desktop"
        alt_dir.mkdir(parents=True)

        paths = config_paths()

        assert tmp_path / ".config" / "Claude" / "claude_desktop_config.json" in paths
        assert alt_dir / "claude_desktop_config.json" in paths

    def test_linux_skips_alt_dir_when_absent(self, tmp_path, monkeypatch):
        monkeypatch.setattr("asher.mcp_config.sys.platform", "linux")
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        paths = config_paths()

        assert paths == [tmp_path / ".config" / "Claude" / "claude_desktop_config.json"]
