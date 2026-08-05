---
name: mcp-bridge
description: How asher-cli's /mcp command and the asher-mcp-launch credential bridge work. Load before changing asher/mcp_config.py, asher/mcp_bridge.py, or the /mcp slash command.
user-invocable: false
---

# MCP bridge (`/mcp`)

pylitterbot ships an optional MCP server (`pip install pylitterbot[mcp]`, run via `python -m pylitterbot.mcp`) that lets an MCP client like Claude Desktop monitor/control the robot directly. Its own docs configure it with plaintext credentials in the client's JSON config — asher-cli avoids that:

- `/mcp on|off|status` (in `asher/commands/__init__.py`, logic in `asher/mcp_config.py`) adds/removes an entry (named by `mcp_config._SERVER_NAME`) in every `claude_desktop_config.json` this OS's Claude Desktop might read (`mcp_config.config_paths()` — on Windows this includes both the standard installer path and any MSIX/Microsoft Store virtualized path). The entry's `command` is `sys.executable -m asher.mcp_bridge` — never the credentials themselves.
- `/mcp on` also auto-installs pylitterbot's `mcp` extra via `sys.executable -m pip install "pylitterbot[mcp]==<installed version>"` if the `mcp` package isn't importable yet.
- `asher/mcp_bridge.py` (console script `asher-mcp-launch`) is what Claude Desktop actually spawns. It reads email/password from the OS keyring at process start, sets them as `LITTER_ROBOT_USERNAME`/`LITTER_ROBOT_PASSWORD` (pylitterbot's expected names — note these differ from asher-cli's own `.env` var `LITTER_ROBOT_USER`) in that process's environment only, then execs `python -m pylitterbot.mcp`. No credentials ever touch the on-disk MCP config.
- `/mcp on` requires keyring credentials. If none are found but `.env` fallback credentials are set, it copies them into the keyring automatically (since the bridge process can't reliably discover a project-relative `.env` — Claude Desktop controls its working directory, not asher-cli).
- Requires the `mcp` extra: `uv sync --extra mcp` / `pip install asher-cli[mcp]`. Restart Claude Desktop after toggling for the change to take effect.
