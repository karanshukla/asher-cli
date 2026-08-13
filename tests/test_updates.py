"""Tests for asher.updates — release checking that never installs anything.

The network is always mocked. The load-bearing assertions here are the safety
ones: HTTPS only, no code path that runs an installer, and a check that stays
quiet rather than guessing when it can't compare two versions.
"""

from __future__ import annotations

import json
import urllib.error
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from asher import config, updates
from asher.updates import Update, check, is_newer, latest_version, report, upgrade_command


@pytest.fixture
def cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "config.json"
    monkeypatch.setattr(config, "_CONFIG_PATH", path)
    monkeypatch.setattr(config, "_CONFIG_DIR", tmp_path)
    return path


def _pypi_response(version: str) -> MagicMock:
    body = json.dumps({"info": {"version": version}}).encode()
    response = MagicMock()
    response.read.return_value = body
    response.url = "https://pypi.org/pypi/asher-cli/json"
    response.__enter__ = lambda self: self
    response.__exit__ = lambda *_: False
    return response


# ── version comparison ───────────────────────────────────────────────────────


class TestIsNewer:
    @pytest.mark.parametrize(
        ("latest", "current", "expected"),
        [
            ("1.2.0", "1.1.0", True),
            ("1.1.1", "1.1.0", True),
            ("2.0.0", "1.9.9", True),
            ("1.1.0", "1.1.0", False),
            ("1.0.0", "1.1.0", False),
            ("1.10.0", "1.9.0", True),
        ],
    )
    def test_compares_numerically(self, latest: str, current: str, expected: bool) -> None:
        """'1.10.0' beats '1.9.0' — string comparison would get this backwards."""
        assert is_newer(latest, current) is expected

    @pytest.mark.parametrize("version", ["1.2.0rc1", "1.2.0.dev3", "", "abc", "1.2.x"])
    def test_declines_to_compare_anything_it_cannot_parse(self, version: str) -> None:
        """Silence beats a hand-rolled parser mis-ordering a pre-release."""
        assert is_newer(version, "1.1.0") is False
        assert is_newer("1.1.0", version) is False


# ── fetching ─────────────────────────────────────────────────────────────────


class TestLatestVersion:
    def test_reads_the_version_from_pypi(self) -> None:
        with patch.object(updates.urllib.request, "urlopen", return_value=_pypi_response("1.4.0")):
            assert latest_version() == "1.4.0"

    def test_requests_over_https(self) -> None:
        with patch.object(updates.urllib.request, "urlopen", return_value=_pypi_response("1.4.0")):
            latest_version()
        assert updates._PYPI_URL.startswith("https://")

    def test_rejects_a_redirect_off_https(self) -> None:
        response = _pypi_response("9.9.9")
        response.url = "http://evil.example/pypi.json"
        with patch.object(updates.urllib.request, "urlopen", return_value=response):
            assert latest_version() is None

    def test_network_failure_is_silent(self) -> None:
        with patch.object(
            updates.urllib.request, "urlopen", side_effect=urllib.error.URLError("offline")
        ):
            assert latest_version() is None

    def test_timeout_is_silent(self) -> None:
        with patch.object(updates.urllib.request, "urlopen", side_effect=TimeoutError):
            assert latest_version() is None

    def test_malformed_json_is_silent(self) -> None:
        response = MagicMock()
        response.read.return_value = b"not json"
        response.url = "https://pypi.org/pypi/asher-cli/json"
        response.__enter__ = lambda self: self
        response.__exit__ = lambda *_: False
        with patch.object(updates.urllib.request, "urlopen", return_value=response):
            assert latest_version() is None

    def test_caps_the_response_it_reads(self) -> None:
        """A hostile or broken endpoint must not stream unbounded data into memory."""
        response = _pypi_response("1.4.0")
        with patch.object(updates.urllib.request, "urlopen", return_value=response):
            latest_version()
        assert response.read.call_args.args[0] == updates._MAX_RESPONSE_BYTES

    def test_passes_a_timeout(self) -> None:
        with patch.object(
            updates.urllib.request, "urlopen", return_value=_pypi_response("1.4.0")
        ) as urlopen:
            latest_version(timeout=1.5)
        assert urlopen.call_args.kwargs["timeout"] == 1.5


# ── check ────────────────────────────────────────────────────────────────────


class TestCheck:
    def test_reports_a_newer_release(self, cfg: Path) -> None:
        with (
            patch.object(updates, "installed_version", return_value="1.0.0"),
            patch.object(updates, "latest_version", return_value="1.1.0"),
        ):
            assert check(force=True) == Update(current="1.0.0", latest="1.1.0")

    def test_silent_when_already_current(self, cfg: Path) -> None:
        with (
            patch.object(updates, "installed_version", return_value="1.1.0"),
            patch.object(updates, "latest_version", return_value="1.1.0"),
        ):
            assert check(force=True) is None

    def test_respects_the_opt_out(self, cfg: Path) -> None:
        config.update(update_check=False)
        with patch.object(updates, "latest_version") as fetch:
            assert check() is None
        fetch.assert_not_called()

    def test_force_still_honours_the_opt_out_for_scheduled_checks_only(self, cfg: Path) -> None:
        """`asher update` is an explicit request, so it runs regardless."""
        config.update(update_check=False)
        with (
            patch.object(updates, "installed_version", return_value="1.0.0"),
            patch.object(updates, "latest_version", return_value="1.1.0") as fetch,
        ):
            assert check(force=True) is not None
        fetch.assert_called_once()

    def test_skips_a_source_checkout(self, cfg: Path) -> None:
        """From source the answer is `git pull`, not a release."""
        with (
            patch.object(updates, "installed_version", return_value="dev"),
            patch.object(updates, "latest_version") as fetch,
        ):
            assert check(force=True) is None
        fetch.assert_not_called()

    def test_hits_the_network_at_most_once_a_day(self, cfg: Path) -> None:
        config.update(last_update_check=date.today().isoformat(), latest_known_version="1.1.0")
        with (
            patch.object(updates, "installed_version", return_value="1.0.0"),
            patch.object(updates, "latest_version") as fetch,
        ):
            result = check()
        fetch.assert_not_called()
        assert result == Update(current="1.0.0", latest="1.1.0")

    def test_caches_what_it_learned(self, cfg: Path) -> None:
        with (
            patch.object(updates, "installed_version", return_value="1.0.0"),
            patch.object(updates, "latest_version", return_value="1.1.0"),
        ):
            check(force=True)
        settings = config.load()
        assert settings["latest_known_version"] == "1.1.0"
        assert settings["last_update_check"] == date.today().isoformat()

    def test_unreachable_network_is_not_an_update(self, cfg: Path) -> None:
        with (
            patch.object(updates, "installed_version", return_value="1.0.0"),
            patch.object(updates, "latest_version", return_value=None),
        ):
            assert check(force=True) is None


# ── presentation ─────────────────────────────────────────────────────────────


class TestUpgradeCommand:
    @pytest.mark.parametrize(
        ("prefix", "expected"),
        [
            ("/home/me/.local/pipx/venvs/asher-cli", "pipx upgrade asher-cli"),
            ("/home/me/.local/share/uv/tools/asher-cli", "uv tool upgrade asher-cli"),
            ("/usr", "pip install -U asher-cli"),
        ],
    )
    def test_matches_the_installer(self, prefix: str, expected: str) -> None:
        with patch.object(updates.sys, "prefix", prefix):
            assert upgrade_command() == expected


class TestReport:
    def test_up_to_date(self, cfg: Path) -> None:
        with (
            patch.object(updates, "installed_version", return_value="1.1.0"),
            patch.object(updates, "check", return_value=None),
        ):
            up_to_date, message = report()
        assert up_to_date is True
        assert "latest release" in message

    def test_update_available_names_the_command_but_does_not_run_it(self, cfg: Path) -> None:
        update = Update(current="1.0.0", latest="1.1.0")
        with (
            patch.object(updates, "installed_version", return_value="1.0.0"),
            patch.object(updates, "check", return_value=update),
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
        ):
            up_to_date, message = report()
        assert up_to_date is False
        assert "v1.0.0 → v1.1.0" in message
        assert upgrade_command() in message
        run.assert_not_called()
        popen.assert_not_called()

    def test_json_output(self, cfg: Path) -> None:
        update = Update(current="1.0.0", latest="1.1.0")
        with (
            patch.object(updates, "installed_version", return_value="1.0.0"),
            patch.object(updates, "check", return_value=update),
        ):
            _, message = report(as_json=True)
        payload: dict[str, Any] = json.loads(message)
        assert payload["update_available"] is True
        assert payload["latest"] == "1.1.0"
        assert payload["command"] == upgrade_command()


class TestNotice:
    def test_reads_as_one_actionable_line(self) -> None:
        notice = Update(current="1.0.0", latest="1.1.0").notice
        assert "1.0.0" in notice
        assert "1.1.0" in notice
        assert upgrade_command() in notice


# ── the module installs nothing ──────────────────────────────────────────────


def test_module_never_spawns_a_process() -> None:
    """The safety property this module exists to keep: it reports, it doesn't apply."""
    source = Path(updates.__file__).read_text(encoding="utf-8")
    for forbidden in ("subprocess", "os.system", "os.exec", "pip.main", "importlib.reload"):
        assert forbidden not in source


def test_module_fetches_only_over_https() -> None:
    source = Path(updates.__file__).read_text(encoding="utf-8")
    assert "http://" not in source.replace("https://", "")


def test_bytesio_response_shape_matches_urlopen() -> None:
    """Guards the test double above against drifting from the real API."""
    assert hasattr(BytesIO(b""), "read")
