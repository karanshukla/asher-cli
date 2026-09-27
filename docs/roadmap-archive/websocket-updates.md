# §6 — Real-time WebSocket updates (replace polling) ✅

> Archived from [`ROADMAP.md`](../ROADMAP.md) §6. The original section text, preserved verbatim.

pylitterbot has first-class WebSocket support:

```python
await robot.subscribe()    # opens WS connection, fires EVENT_UPDATE
await robot.unsubscribe()
```

On `EVENT_UPDATE` the robot's properties update automatically — no polling
needed. The `_poll_status_interval` timer could be replaced with:

```python
robot.on(EVENT_UPDATE, lambda: asyncio.create_task(self._refresh_status()))
await robot.subscribe()
```

**Why this matters:** the current 30 s polling means the UI is always up to 30 s
stale. WebSocket gives instant updates — the drawer fill jumps as soon as the
cloud sees it, and a cleaning cycle starting shows immediately in the status bar.
