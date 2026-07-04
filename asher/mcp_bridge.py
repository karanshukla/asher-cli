"""Launcher for pylitterbot's MCP server, run by an MCP client (e.g. Claude Desktop).

Reads credentials from the OS keyring — the same store asher-cli itself uses — and
passes them to pylitterbot's MCP server as environment variables held only in this
process's memory. The MCP client's on-disk config never contains a plaintext
username or password; it just points here.
"""

from __future__ import annotations

import os
import subprocess
import sys

_SERVICE = "asher-cli"


def main() -> None:
    import keyring

    email = keyring.get_password(_SERVICE, "email") or ""
    password = keyring.get_password(_SERVICE, "password") or ""

    if not email or not password:
        print(
            "asher-mcp-launch: no credentials found in the OS keyring. "
            "Run asher-cli and sign in with /login at least once, then retry.",
            file=sys.stderr,
        )
        sys.exit(1)

    env = os.environ.copy()
    env["LITTER_ROBOT_USERNAME"] = email
    env["LITTER_ROBOT_PASSWORD"] = password

    result = subprocess.run([sys.executable, "-m", "pylitterbot.mcp"], env=env, check=False)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
