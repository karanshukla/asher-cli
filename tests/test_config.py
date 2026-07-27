"""Tests for asher.config — JSON load/save over defaults.

Mirrors the style of ``tests/test_mcp_config.py``: real JSON I/O against
``tmp_path`` via a patched module path constant, no Textual or pylitterbot
dependency. ``config.py`` is pure stdlib so every test is synchronous.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from asher import config
from asher.config import _DEFAULTS, config_path, load, save, update


@pytest.fixture
def cfg_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect config I/O to a tmp file so tests never touch the real home dir."""
    path = tmp_path / "config.json"
    monkeypatch.setattr(config, "_CONFIG_PATH", path)
    monkeypatch.setattr(config, "_CONFIG_DIR", tmp_path)
    return path


# ── load ──────────────────────────────────────────────────────────────────────


class TestLoad:
    def test_missing_file_returns_defaults(self, cfg_path: Path) -> None:
        assert load() == _DEFAULTS

    def test_valid_file_overrides_defaults(self, cfg_path: Path) -> None:
        cfg_path.write_text(
            json.dumps(
                {
                    "poll_interval_seconds": 60,
                    "cat_panel_visible": False,
                    "cat_panel_color": "#ff79c6",
                    "active_pet_index": 2,
                }
            ),
            encoding="utf-8",
        )
        data = load()
        assert data["poll_interval_seconds"] == 60
        assert data["cat_panel_visible"] is False
        assert data["cat_panel_color"] == "#ff79c6"
        assert data["active_pet_index"] == 2

    def test_corrupt_json_returns_defaults(self, cfg_path: Path) -> None:
        cfg_path.write_text("{not valid json", encoding="utf-8")
        assert load() == _DEFAULTS

    def test_partial_file_merges_with_defaults(self, cfg_path: Path) -> None:
        cfg_path.write_text(json.dumps({"poll_interval_seconds": 10}), encoding="utf-8")
        data = load()
        assert data["poll_interval_seconds"] == 10
        assert data["cat_panel_visible"] is True
        assert data["cat_panel_color"] is None
        assert data["active_pet_index"] == 0

    def test_unknown_keys_in_file_are_ignored(self, cfg_path: Path) -> None:
        cfg_path.write_text(
            json.dumps({"poll_interval_seconds": 15, "stale_key": "ignored"}), encoding="utf-8"
        )
        data = load()
        assert "stale_key" not in data
        assert data["poll_interval_seconds"] == 15

    def test_null_color_read_back_as_none(self, cfg_path: Path) -> None:
        cfg_path.write_text(json.dumps({"cat_panel_color": None}), encoding="utf-8")
        assert load()["cat_panel_color"] is None

    def test_non_dict_json_returns_defaults(self, cfg_path: Path) -> None:
        cfg_path.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
        assert load() == _DEFAULTS

    def test_returns_a_copy_not_the_defaults_object(self, cfg_path: Path) -> None:
        data = load()
        data["poll_interval_seconds"] = 999
        assert _DEFAULTS["poll_interval_seconds"] == 300


# ── save ──────────────────────────────────────────────────────────────────────


class TestSave:
    def test_round_trip(self, cfg_path: Path) -> None:
        settings = {
            "poll_interval_seconds": 45,
            "cat_panel_visible": False,
            "cat_panel_color": "#abc123",
            "active_pet_index": 1,
        }
        save(settings)
        on_disk = json.loads(cfg_path.read_text(encoding="utf-8"))
        assert on_disk == settings
        assert load() == settings

    def test_creates_parent_dir_when_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        nested = tmp_path / "nested" / "deeper" / "config.json"
        monkeypatch.setattr(config, "_CONFIG_PATH", nested)
        monkeypatch.setattr(config, "_CONFIG_DIR", nested.parent)
        save({"poll_interval_seconds": 30})
        assert nested.exists()
        assert json.loads(nested.read_text(encoding="utf-8"))["poll_interval_seconds"] == 30

    def test_writes_indented_json_with_trailing_newline(self, cfg_path: Path) -> None:
        save(_DEFAULTS)
        raw = cfg_path.read_text(encoding="utf-8")
        assert raw.endswith("\n")
        assert '\n  "' in raw  # indent=2 produces a newline + two spaces before a key

    def test_save_does_not_merge_defaults(self, cfg_path: Path) -> None:
        save({"poll_interval_seconds": 99})
        on_disk = json.loads(cfg_path.read_text(encoding="utf-8"))
        assert on_disk == {"poll_interval_seconds": 99}


# ── update ────────────────────────────────────────────────────────────────────


class TestUpdate:
    def test_partial_update_preserves_other_fields(self, cfg_path: Path) -> None:
        update(poll_interval_seconds=120)
        update(cat_panel_color="#ff79c6")
        data = load()
        assert data["poll_interval_seconds"] == 120
        assert data["cat_panel_color"] == "#ff79c6"
        assert data["cat_panel_visible"] is True
        assert data["active_pet_index"] == 0

    def test_returns_full_merged_dict(self, cfg_path: Path) -> None:
        result = update(active_pet_index=3)
        assert result["active_pet_index"] == 3
        assert result["poll_interval_seconds"] == 300

    def test_multiple_updates_in_sequence(self, cfg_path: Path) -> None:
        update(poll_interval_seconds=10)
        update(cat_panel_visible=False)
        update(cat_panel_color=None)
        update(active_pet_index=1)
        data = load()
        assert data == {
            "poll_interval_seconds": 10,
            "cat_panel_visible": False,
            "cat_panel_color": None,
            "active_pet_index": 1,
        }

    def test_update_writes_through_to_disk(self, cfg_path: Path) -> None:
        update(poll_interval_seconds=60)
        on_disk = json.loads(cfg_path.read_text(encoding="utf-8"))
        assert on_disk["poll_interval_seconds"] == 60


# ── config_path ───────────────────────────────────────────────────────────────


class TestConfigPath:
    def test_returns_resolved_path(self) -> None:
        path = config_path()
        assert path.name == "config.json"
        assert path.parent.name == ".asher-cli"


# ── wiring: AsherApp.__init__ reads from config.load() ────────────────────────


class TestAppWiring:
    def test_init_reads_persisted_values(self) -> None:
        """AsherApp.__init__ should read its four runtime settings from config.load()."""
        from asher.app import AsherApp

        fake_cfg = {
            "poll_interval_seconds": 42,
            "cat_panel_visible": False,
            "cat_panel_color": "#deadbe",
            "active_pet_index": 7,
        }
        with (
            patch("asher.connection._keyring_available", return_value=False),
            patch("os.getenv", return_value=""),
            patch("asher.config.load", return_value=fake_cfg),
        ):
            app = AsherApp()
        assert app._poll_interval == 42
        assert app._cat_panel_visible is False
        assert app._cat_color == "#deadbe"
        assert app._active_pet_idx == 7

    def test_init_falls_back_to_defaults_when_load_returns_defaults(self) -> None:
        from asher.app import AsherApp

        with (
            patch("asher.connection._keyring_available", return_value=False),
            patch("os.getenv", return_value=""),
            patch("asher.config.load", return_value=dict(_DEFAULTS)),
        ):
            app = AsherApp()
        assert app._poll_interval == 300
        assert app._cat_panel_visible is True
        assert app._cat_color is None
        assert app._active_pet_idx == 0


# ── wiring: _persist helper swallows OSError ──────────────────────────────────


class TestPersistHelper:
    def test_persist_calls_config_update(self) -> None:
        from asher.commands import _persist

        app = MagicMock()
        with patch("asher.config.update", return_value={}) as mock_update:
            _persist(app, poll_interval_seconds=99)
        mock_update.assert_called_once_with(poll_interval_seconds=99)
        app._log_warn.assert_not_called()

    def test_persist_logs_warning_on_oserror(self) -> None:
        from asher.commands import _persist

        app = MagicMock()
        with patch("asher.config.update", side_effect=OSError("read-only")):
            _persist(app, cat_panel_visible=False)
        app._log_warn.assert_called_once()
        assert "read-only" in app._log_warn.call_args[0][0]


# ── wiring: slash commands call _persist ──────────────────────────────────────


def _stub_app() -> Any:
    """A real AsherApp with DOM-touching methods stubbed, so command handlers
    run without a mounted screen (no ``run_test()`` harness needed)."""
    from asher.app import AsherApp

    with (
        patch("asher.connection._keyring_available", return_value=False),
        patch("os.getenv", return_value=""),
        patch("asher.config.load", return_value=dict(_DEFAULTS)),
    ):
        app = AsherApp()
    # Command handlers call these; without a screen they'd raise ScreenStackError.
    app._log_ok = MagicMock()  # type: ignore[method-assign]
    app._log_info = MagicMock()  # type: ignore[method-assign]
    app._log_warn = MagicMock()  # type: ignore[method-assign]
    app._set_cat = MagicMock()  # type: ignore[method-assign]
    app._refresh_status = AsyncMock(return_value=None)  # type: ignore[method-assign]
    app.query_one = MagicMock()  # type: ignore[method-assign]
    app.set_interval = MagicMock(return_value=MagicMock())  # type: ignore[method-assign]
    return app


class TestSlashCommandPersistence:
    """Smoke tests: the slash commands that mutate persisted state call _persist."""

    async def test_refresh_persists_interval(self) -> None:
        from asher.commands import RefreshCommand

        app = _stub_app()
        app._poll_timer = None
        with patch("asher.commands._persist") as mock_persist:
            await RefreshCommand().run(app, ["30"])
        mock_persist.assert_called_once_with(app, poll_interval_seconds=30)
        assert app._poll_interval == 30

    async def test_refresh_off_persists_zero(self) -> None:
        from asher.commands import RefreshCommand

        app = _stub_app()
        app._poll_timer = MagicMock()
        with patch("asher.commands._persist") as mock_persist:
            await RefreshCommand().run(app, ["off"])
        mock_persist.assert_called_once_with(app, poll_interval_seconds=0)
        assert app._poll_interval == 0

    async def test_cat_color_persists(self) -> None:
        from asher.commands import CatCommand

        app = _stub_app()
        with patch("asher.commands._persist") as mock_persist:
            await CatCommand().run(app, ["color", "ff79c6"])
        mock_persist.assert_called_once_with(app, cat_panel_color="#ff79c6")
        assert app._cat_color == "#ff79c6"

    async def test_cat_reset_persists_none(self) -> None:
        from asher.commands import CatCommand

        app = _stub_app()
        with patch("asher.commands._persist") as mock_persist:
            await CatCommand().run(app, ["reset"])
        mock_persist.assert_called_once_with(app, cat_panel_color=None)
        assert app._cat_color is None

    async def test_cat_off_persists_visibility(self) -> None:
        from asher.commands import CatCommand

        app = _stub_app()
        with patch("asher.commands._persist") as mock_persist:
            await CatCommand().run(app, ["off"])
        mock_persist.assert_called_once_with(app, cat_panel_visible=False)
        assert app._cat_panel_visible is False

    async def test_pet_index_persists(self) -> None:
        from asher.commands import PetCommand

        app = _stub_app()
        app._pets = [MagicMock(name="Asher"), MagicMock(name="Luna")]
        with patch("asher.commands._persist") as mock_persist:
            await PetCommand().run(app, ["1"])
        mock_persist.assert_called_once_with(app, active_pet_index=1)
        assert app._active_pet_idx == 1
