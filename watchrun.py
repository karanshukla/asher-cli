"""Dev watcher: monitors asher/ for Python changes and restarts the app cleanly."""

import contextlib
import os
import shutil
import signal
import subprocess
import sys

from watchfiles import PythonFilter, watch

_UV = shutil.which("uv") or "uv"

if sys.platform == "win32":
    _TASKKILL = shutil.which("taskkill") or "taskkill"

    def _start() -> subprocess.Popen:  # type: ignore[misc]
        return subprocess.Popen(  # nosec B603 # fixed argv, no shell
            [_UV, "run", "--no-sync", "python", "-m", "asher"],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )

    def _kill(proc: subprocess.Popen) -> None:  # type: ignore[misc]
        if proc.poll() is not None:
            return
        with contextlib.suppress(OSError):
            os.kill(proc.pid, signal.CTRL_BREAK_EVENT)
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=3)
        if proc.poll() is None:
            subprocess.run(  # nosec B603 # fixed argv, no shell
                [_TASKKILL, "/T", "/F", "/PID", str(proc.pid)], capture_output=True
            )
            proc.wait()

else:

    def _start() -> subprocess.Popen:
        return subprocess.Popen(  # nosec B603 # fixed argv, no shell
            [_UV, "run", "--no-sync", "python", "-m", "asher"],
            start_new_session=True,
        )

    def _kill(proc: subprocess.Popen) -> None:
        if proc.poll() is not None:
            return
        with contextlib.suppress(OSError):
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=3)
        if proc.poll() is None:
            proc.kill()
            proc.wait()


proc = _start()
try:
    for _ in watch("asher", watch_filter=PythonFilter(), ignore_paths=["asher/__pycache__"]):
        _kill(proc)
        proc = _start()
except KeyboardInterrupt:
    _kill(proc)
