# Contributing to Asher CLI

Process and reference material: dev setup, tests, CI, versioning, releasing.
What's left to build lives in [`ROADMAP.md`](ROADMAP.md); code conventions
(command registries, colour, credentials) live in [`CLAUDE.md`](../CLAUDE.md).

---

## Dev setup

```bash
uv sync            # dev + tray groups (see CLAUDE.md § Tray packaging)
uv run asher       # or: uv run python -m asher
uv run poe check   # lint → fmt → types → test, same as CI
```

Other `poe` tasks (`[tool.poe.tasks]` in `pyproject.toml`): `lint`, `fmt`,
`types`, `test`, `security` (the Bandit scan), `fix` (ruff autofix + format),
`dev` (`textual run --dev`).

The pre-push hook (`.githooks/pre-push`) runs ruff check → ruff format --check
→ mypy. Tests aren't in the hook — run them yourself.

### Installing without a clone

For end users `pipx install asher-cli` or `uv tool install asher-cli` (README
§ Install). To try it without installing anything, `uvx --from asher-cli asher`
runs it from a throwaway environment.

---

## Testing

```bash
uv run pytest                                      # everything
uv run pytest --cov=asher --cov-report=term-missing
```

- **Unit** — pure modules (`asher/core/helpers.py`, `asher/core/activity.py`,
  `asher/core/faults.py`, `asher/core/export.py`, `asher/robot/adapters.py`, …)
  tested directly, no Textual or event loop.
- **Integration / E2E** — Textual's `Pilot` harness (`app.run_test()`) drives
  the real command bar (`pilot.press(...)`) against the `mock_robot` /
  `mock_account` `AsyncMock` fixtures in `tests/conftest.py`, asserting on side
  effects: robot API calls, log content, keyring writes, cat mode. Only the
  pylitterbot layer is mocked, never Textual.
- **Headless** — `tests/test_headless.py` runs every `COMMANDS` handler against
  mock robots plus the argparse surface and exit codes.
- **Layering** — `tests/test_layering.py` guards the package boundaries.

Per-file descriptions are in `CLAUDE.md` § Package structure. Pilot gotchas are
in `CLAUDE.md` § Testing notes.

CI matrix: Python 3.10 / 3.11 / 3.12 × Ubuntu / Windows / macOS.

### Coverage

`pytest-cov` with `[tool.coverage.run]` / `[tool.coverage.report]` in
`pyproject.toml`. `.github/workflows/coverage.yml` runs daily (06:00 UTC, plus
manual dispatch) and uploads to Coveralls (badge in the README).

Targets by layer:

| Layer | Target | Notes |
|---|---|---|
| `asher/core/` | ≥ 90% | Mostly pure; `helpers.py` should be 100% |
| `asher/robot/` | ≥ 90% | Mock robot per model |
| `asher/tui/commands/` | ≥ 80% | Cover each command branch |
| `asher/tui/connection.py` | ≥ 70% | Mock keyring + `pylitterbot.Account` |
| `asher/tui/monitoring.py` | ≥ 70% | Mock robot; WebSocket + poll paths |
| `asher/tui/ui.py` | ≥ 50% | Pilot covers compose/log helpers |

---

## Code quality gates

| Tool | Purpose | Config |
|---|---|---|
| `ruff` | Lint + format | `[tool.ruff]` in `pyproject.toml` |
| `mypy` | Static types | `[tool.mypy]` |
| `pytest` | Tests | `[tool.pytest.ini_options]` |
| `bandit` | Security scan → code scanning (SARIF) | `[tool.bandit]`; `uv run poe security` locally |
| Renovate | Dependency freshness | `renovate.json` |

No `assert` in `asher/` — Bandit's B101 is on for shipped code.

---

## CI / CD

| Workflow | Trigger | Does |
|---|---|---|
| `ci.yml` | push to `main`, every PR | `lint` (ruff check, ruff format --check, mypy) → `test` matrix |
| `coverage.yml` | daily cron, manual | coverage report → Coveralls |
| `bandit.yml` | push to `main`/`release/*`, PRs to `main`, weekly | Bandit → SARIF → code scanning |
| `release.yml` | push to `release/*` | build → publish to PyPI → GitHub Release |
| `dependency-automerge.yml` | Renovate PRs | auto-merge once checks pass |

CI syncs with `uv sync --no-default-groups --group dev` and sets
`UV_NO_SYNC=1`: the default `tray` group pulls in PyGObject, which builds from
source and the runners have no GObject-introspection headers.

Actions are pinned to commit SHAs. Read the workflow files for the
authoritative versions — a YAML copy pasted into docs drifts.

### Renovate

Weekly (Monday mornings). Enabled for `pylitterbot` (the only Python dep
Renovate touches — it's pinned exact in `pyproject.toml`, since the Whisker API
is reverse-engineered and any bump can change names or response shapes) and for
GitHub Actions digests. Patch/minor/digest/pin updates auto-merge once required
checks pass; majors get manual review.

### Branches

```
main            always releasable; protected, requires passing CI
feat/* fix/*    work branches; merge via PR with squash
release/X.Y.Z   cut from main after the version bump; pushing it publishes
```

Protect `main`: require a PR, require CI, no force-push.

### Pull requests

Use [`.github/pull_request_template.md`](../.github/pull_request_template.md).
Commit messages must be conventional (`feat:`, `fix(robot):`, `docs:`, …) or
git-cliff won't file them in the changelog.

---

## Versioning

Version lives only in `pyproject.toml`. Everything else reads it via
`importlib.metadata.version("asher-cli")`, falling back to `"dev"` when running
from source without an install — never hard-code a version string.

Semantic versioning:

- **PATCH** — bug fixes, dependency pin updates
- **MINOR** — new commands, config keys, widgets
- **MAJOR** — a command renamed/removed, or the config schema breaks

`bump-my-version` (`[tool.bumpversion]`) rewrites `pyproject.toml`, re-locks
with `uv lock`, commits, and tags `vX.Y.Z` in one step. The release workflow
keys off the `release/*` *branch* name, not the tag.

### Changelog

`CHANGELOG.md` is generated by [git-cliff](https://git-cliff.org) from
conventional commits (`cliff.toml`), Keep a Changelog format. The release job
lifts the `## [X.Y.Z]` section out of the committed file **verbatim** for the
GitHub Release body, and fails if it's missing.

- `poe changelog` — regenerate with pending commits under `## [Unreleased]`.
- `poe changelog-release X.Y.Z` — file them under `## [X.Y.Z]`. Use this one
  when cutting a release.

Both regenerate the whole file from commits, so hand-refinements to a section
are lost if either task is re-run afterwards. Refine last.

---

## Releasing

Follow README § Releasing exactly, in order:

1. `uv run poe check` — all green.
2. `uv run poe changelog-release X.Y.Z`, refine the prose if a squashed commit
   needs unpacking, then commit it
   (`git commit -am "docs(changelog): cut vX.Y.Z"`). Don't re-run either
   changelog task after refining.
3. `uv run bump-my-version bump patch|minor|major` — commits **and tags**.
4. `git push && git push --tags`
5. Only then: `git checkout -b release/X.Y.Z && git push origin release/X.Y.Z`
   — triggers the PyPI publish and the GitHub Release.

### What `release.yml` does

1. **build** — `uv build` (wheel + sdist), uploads `dist/`.
2. **publish** — `pypa/gh-action-pypi-publish` with OIDC trusted publishing
   (`karanshukla/asher-cli` → `release.yml` → `pypi` environment). No stored
   API token.
3. **github-release** — extracts `## [X.Y.Z]` from `CHANGELOG.md` and runs
   `gh release create vX.Y.Z` with the built wheel/sdist attached.

### Testing a build before release

```bash
uv build                                   # → dist/asher_cli-X.Y.Z-py3-none-any.whl + .tar.gz
pipx install ./dist/asher_cli-X.Y.Z-py3-none-any.whl --force
asher --help        # then run it against your account before cutting
```

### Hotfix

Branch from the last release branch; don't touch `main`:

```bash
git checkout release/X.Y.Z
git checkout -b release/X.Y.(Z+1)
# cherry-pick the fix, cut the changelog section, bump
git push origin release/X.Y.(Z+1)   # → publishes
```
