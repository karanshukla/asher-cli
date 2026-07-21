"""Pilot tests for the /version slash command (§24)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from asher.app import AsherApp


@pytest.fixture
def app_no_connect():
    """An AsherApp with the background _connect_worker stubbed out."""
    app = AsherApp()
    app._account = MagicMock()
    app._account.disconnect = AsyncMock()
    app._pets = []
    app._connect_worker = lambda **kwargs: None  # type: ignore[method-assign]
    return app


def _log_text(app: AsherApp) -> str:
    return str(app.query_one("#log").lines)


async def _type(pilot, text: str) -> None:
    for ch in text:
        await pilot.press(ch)
    await pilot.press("enter")


@pytest.mark.asyncio
async def test_version_prints_package_versions(app_no_connect):
    async with app_no_connect.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "/version")
        await pilot.pause()
        await pilot.pause()

        log = _log_text(app_no_connect)

    # asher-cli resolves from importlib.metadata (installed editable in tests).
    assert "asher-cli" in log.lower() or "asher cli" in log.lower()
    # Python line is always present.
    assert "python" in log.lower()
    # Dependency versions.
    assert "pylitterbot" in log.lower()
    assert "textual" in log.lower()


@pytest.mark.asyncio
async def test_version_shows_v_prefix(app_no_connect):
    async with app_no_connect.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "/version")
        await pilot.pause()
        await pilot.pause()

        log = _log_text(app_no_connect)

    # The asher-cli line is formatted "Asher CLI v<x.y.z>".
    assert "Asher CLI v" in log


@pytest.mark.asyncio
async def test_version_handles_missing_package(app_no_connect):
    """PackageNotFoundError should fall back to '?' rather than crashing."""
    from importlib.metadata import PackageNotFoundError

    def _raise(pkg):
        raise PackageNotFoundError(pkg)

    with patch("asher.commands.pkg_version", side_effect=_raise):
        async with app_no_connect.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#cmd-input")
            await _type(pilot, "/version")
            await pilot.pause()
            await pilot.pause()

            log = _log_text(app_no_connect)

    # Unknown packages render '?' instead of raising.
    assert "?" in log
