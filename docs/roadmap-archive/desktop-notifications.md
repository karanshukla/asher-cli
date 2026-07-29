# §22 — Desktop notifications ✅

> Archived from [`ROADMAP.md`](../ROADMAP.md) §22. The original section text, preserved verbatim.

Yes, a CLI app can push OS-level toast notifications — the terminal doesn't need
to be in focus. The approach depends on platform but `plyer` abstracts it cleanly.

### How it works

```python
from plyer import notification   # pip install plyer

notification.notify(
    title="Asher — Cat Detected",
    message="Cycle halted at 14:32. Check the litter box.",
    app_name="Asher CLI",
    timeout=8,          # seconds before auto-dismiss
)
```

That's it. On Windows this fires a native Action Center toast. On macOS it goes
through Notification Center. On Linux it uses `libnotify` (`notify-send`).

### Installation

```bash
pip install plyer
```

Add to `pyproject.toml`:
```toml
dependencies = [
    ...
    "plyer>=2.1",
]
```

`plyer` is pure-Python with no C extensions — no binary complications for
PyInstaller packaging.

### When to notify

Only notify on **state transitions** (fault appeared, not "fault is still
active"). Wire into `_refresh_faults` from §9c:

```python
from plyer import notification as _notify

NOTIFY_EVENTS = {
    "CAT DETECTED — cycle halted":          ("Asher — Cat Detected",    8),
    "PINCH DETECT — possible obstruction":  ("Asher — Safety Cutoff",   10),
    "GLOBE MOTOR FAULT":                    ("Asher — Motor Fault",      0),  # 0 = persistent
    "DRAWER FULL — empty now":              ("Asher — Drawer Full",      8),
}

def _refresh_faults(self, robot) -> None:
    current = set(label for label, _ in self._check_faults(robot))
    for label in current - self.prev_faults:           # newly appeared
        self._log_err(f"FAULT: {label}")
        if label in NOTIFY_EVENTS:
            title, timeout = NOTIFY_EVENTS[label]
            _notify.notify(title=title, message=label,
                           app_name="Asher CLI", timeout=timeout)
    for label in self.prev_faults - current:           # cleared
        self._log_ok(f"Cleared: {label}")
    self.prev_faults = current
```

### Sound alert alongside the toast

On Windows, `winsound` is stdlib (no install needed):

```python
import sys, winsound

def _alert_sound(critical: bool = False) -> None:
    if sys.platform != "win32":
        print("\a", end="", flush=True)   # terminal bell on macOS/Linux
        return
    freq = 880 if critical else 440
    winsound.Beep(freq, 300)
```

Call `_alert_sound(critical=True)` for pinch/cat-detected, `_alert_sound()` for
drawer-full and hardware faults.

### `/notify` slash command — opt-in control

```
/notify           show current notification settings
/notify on        enable desktop notifications (default)
/notify off       disable all notifications
/notify sound off disable sound only
/notify test      fire a test notification immediately
```

Persist the preference in `config.json` (§10):
```json
{ "notifications": true, "notification_sound": true }
```

### Platform note (Windows-specific refinement)

`plyer` on Windows uses `win10toast` under the hood, which works fine but
produces older-style balloon tips on some Windows 11 builds. For a sharper
Windows 11 toast (with the app icon and action buttons), `winotify` is a
drop-in upgrade:

```python
try:
    from winotify import Notification, audio   # pip install winotify
    def _toast(title, msg, timeout):
        n = Notification(app_id="Asher CLI", title=title, msg=msg, duration="short")
        n.set_audio(audio.Default, loop=False)
        n.show()
except ImportError:
    from plyer import notification as _plyer
    def _toast(title, msg, timeout):
        _plyer.notify(title=title, message=msg, app_name="Asher CLI", timeout=timeout)
```

`winotify` is Windows-only; the `ImportError` fallback keeps the code
cross-platform.
