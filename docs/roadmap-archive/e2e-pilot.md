# §17 — Testing — E2E Textual Pilot harness ✅

> Archived from [`ROADMAP.md`](../ROADMAP.md) §17. The shipped subsections only — what's still open stays in the roadmap. Original text, preserved verbatim.

### E2E — Textual Pilot harness

Textual ships a `Pilot` test harness that drives the full TUI — keypresses,
widget queries, and assertions — without a real terminal. No extra install
needed; it's part of `textual` itself.

```python
# tests/teste2e.py
import pytest
from asher.app import AsherApp

@pytest.mark.asyncio
async def test_help_renders():
    async with AsherApp().run_test() as pilot:
        await pilot.press("h", "e", "l", "p", "enter")
        log = pilot.app.query_one("#log")
        content = str(log.renderable)
        assert "clean" in content
        assert "/login" in content

@pytest.mark.asyncio
async def test_quit_exits():
    async with AsherApp().run_test() as pilot:
        await pilot.press("q", "enter")
        assert pilot.app._exit  # app exited cleanly

@pytest.mark.asyncio
async def test_clear_empties_log():
    async with AsherApp().run_test() as pilot:
        await pilot.press("c", "l", "e", "a", "r", "enter")
        log = pilot.app.query_one("#log")
        assert str(log.renderable).strip() == ""
```

The key `run_test()` context manager boots the full app headlessly, fires the
compose/mount lifecycle, and lets tests assert on real widget state. No mocking
of Textual internals required — only the pylitterbot layer needs mocking.

**Mocking the connection in E2E tests:**

```python
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_status_bar_updates_on_connect(mock_robot, mock_account):
    with patch("asher.connection.Account", return_value=mock_account):
        async with AsherApp().run_test() as pilot:
            await pilot.pause(0.1)   # let _connect_worker finish
            lbl = pilot.app.query_one("#online-lbl").renderable
            assert "ONLINE" in str(lbl)
```
