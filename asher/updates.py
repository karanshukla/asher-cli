"""Tell the user a new release exists. Never install one.

Asher installs through pipx, pip, or ``uv tool``, and the process has no
reliable way to know which — so a self-upgrade would be guessing at the command
that owns its own files. Worse, this package lazy-imports throughout (every
``# noqa: PLC0415``), so replacing its files under a live interpreter can load a
mix of old and new modules. The background watcher makes that worse again: it
is a long-lived process, so it would be the one running while its own code is
swapped out.

The deciding argument is trust, not mechanics. Installing on the user's behalf
turns one compromised release into code running on every machine that has the
tool, with nobody having chosen the moment. Checking is safe; applying is the
user's call.

So this module does exactly one thing: read the latest published version from
PyPI's JSON API over HTTPS and compare it with the installed one. Read-only,
no code fetched or executed, at most one request a day, and ``update_check:
false`` in the config turns it off entirely.
"""

from __future__ import annotations

import contextlib
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import config

_PYPI_URL = "https://pypi.org/pypi/asher-cli/json"
_RELEASES_URL = "https://github.com/karanshukla/asher-cli/releases"
_TIMEOUT_SECONDS = 3.0
_MAX_RESPONSE_BYTES = 1_000_000


@dataclass(frozen=True)
class Update:
    """A newer release than the one running."""

    current: str
    latest: str

    @property
    def notice(self) -> str:
        return f"Update available: v{self.current} → v{self.latest}  ({upgrade_command()})"


def installed_version() -> str:
    from importlib.metadata import PackageNotFoundError  # noqa: PLC0415
    from importlib.metadata import version as pkg_version  # noqa: PLC0415

    try:
        return pkg_version("asher-cli")
    except PackageNotFoundError:
        return "dev"


def _parse(version: str) -> tuple[int, ...] | None:
    """Parse a plain ``X.Y.Z`` version into comparable integers.

    Deliberately narrow: this project tags plain three-part versions, and a
    hand-rolled parser that quietly mis-orders a pre-release would be worse than
    one that declines to compare it at all. Anything else returns None and is
    treated as "can't tell", which reports no update.
    """
    parts = version.strip().split(".")
    if not all(part.isdigit() for part in parts) or not parts:
        return None
    return tuple(int(part) for part in parts)


def is_newer(latest: str, current: str) -> bool:
    """Whether ``latest`` is a later release than ``current``."""
    latest_parts, current_parts = _parse(latest), _parse(current)
    if latest_parts is None or current_parts is None:
        return False
    return latest_parts > current_parts


def latest_version(timeout: float = _TIMEOUT_SECONDS) -> str | None:
    """Fetch the newest published version from PyPI, or None if unreachable.

    HTTPS only, and urllib verifies the certificate chain against the system
    trust store by default. The scheme is asserted rather than assumed because
    a redirect is the one way this could otherwise end up reading plaintext.
    """
    request = urllib.request.Request(  # noqa: S310 — literal https URL, asserted below
        _PYPI_URL, headers={"Accept": "application/json", "User-Agent": "asher-cli"}
    )
    if request.type != "https":
        return None
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
            if response.url and not response.url.startswith("https://"):
                return None
            payload = json.loads(response.read(_MAX_RESPONSE_BYTES).decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return None
    version = payload.get("info", {}).get("version") if isinstance(payload, dict) else None
    return version if isinstance(version, str) else None


def check(*, force: bool = False) -> Update | None:
    """Return an available update, or None.

    Throttled to one network request per day via the config file, and skipped
    entirely when ``update_check`` is off or the package is running from a source
    checkout (where the answer is ``git pull``, not a release).
    """
    settings = config.load()
    if not force and not settings.get("update_check", True):
        return None

    current = installed_version()
    if current == "dev":
        return None

    today = date.today().isoformat()
    if not force and settings.get("last_update_check") == today:
        known = settings.get("latest_known_version")
        if isinstance(known, str) and is_newer(known, current):
            return Update(current=current, latest=known)
        return None

    latest = latest_version()
    if latest is None:
        return None
    with contextlib.suppress(OSError):
        config.update(last_update_check=today, latest_known_version=latest)
    return Update(current=current, latest=latest) if is_newer(latest, current) else None


def upgrade_command() -> str:
    """The upgrade command for however this copy was installed.

    Detected from the interpreter's own location, because the installer doesn't
    record itself anywhere: pipx and ``uv tool`` each put their virtualenvs under
    a recognisable directory. Everything else falls back to pip, which is the
    right answer for a plain ``pip install`` and a harmless suggestion otherwise.
    """
    prefix = Path(sys.prefix).as_posix()
    if "/pipx/venvs/" in prefix:
        return "pipx upgrade asher-cli"
    if "/uv/tools/" in prefix:
        return "uv tool upgrade asher-cli"
    return "pip install -U asher-cli"


def releases_url() -> str:
    """Where to read what actually changed before upgrading."""
    return _RELEASES_URL


def report(as_json: bool = False) -> tuple[bool, str]:
    """Render ``asher update`` output. Returns ``(up_to_date, message)``."""
    current = installed_version()
    update = check(force=True)
    if update is None:
        data = {"current": current, "update_available": False}
        text = f"asher-cli v{current} is the latest release."
    else:
        data = {
            "current": current,
            "latest": update.latest,
            "update_available": True,
            "command": upgrade_command(),
            "changelog": releases_url(),
        }
        text = "\n".join(
            [
                f"Update available: v{current} → v{update.latest}",
                f"  run:       {upgrade_command()}",
                f"  changelog: {releases_url()}",
            ]
        )
    return update is None, json.dumps(data, indent=2) if as_json else text
