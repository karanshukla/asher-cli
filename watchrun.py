"""Dev watcher target: run app, exit watchfiles when app exits cleanly."""

import contextlib
import os
import signal
import subprocess

result = subprocess.run(["uv", "run", "--no-sync", "textual", "run", "--dev", "asher.app:AsherApp"])
if result.returncode == 0:
    # User exited the app cleanly — stop the watchfiles watcher too
    with contextlib.suppress(ProcessLookupError):
        os.kill(os.getppid(), signal.SIGTERM)
