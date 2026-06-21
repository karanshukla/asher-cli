---
name: release
description: Cut a new asher-cli release. Runs preflight checks, bumps the version with bump-my-version, pushes the tag, and confirms the GitHub Actions release workflow is triggered. Invoke when user says "release", "cut a release", "bump version", "publish", or "ship".
disable-model-invocation: true
---

# Release Skill

Walk through the release process in order. Stop and report if any step fails.

## Steps

1. **Check working tree is clean**
   Run `git status --porcelain`. If there are uncommitted changes, stop and tell the user to commit or stash them first.

2. **Run full CI checks locally**
   Run `uv run poe check` (lint + format + types + tests). All must pass before bumping.

3. **Confirm the bump level**
   Ask the user: patch / minor / major? Default to `patch` for bug fixes, `minor` for new features.

4. **Bump the version**
   Run `uv run bump-my-version bump <level>`.
   This automatically:
   - Updates `version` in `pyproject.toml`
   - Runs `uv lock --no-sync` (pre-commit hook)
   - Stages `uv.lock` and commits with a version bump message
   - Creates a git tag `v<new_version>`

5. **Push the commit and tag**
   Run `git push origin main --tags`.
   The `release.yml` GitHub Actions workflow triggers on new tags matching `v*`.

6. **Confirm the workflow triggered**
   Run `gh run list --workflow=release.yml --limit=3` and show the user the latest run status.

7. **Report done**
   Show the new version number and the expected PyPI URL once the workflow completes.

## Notes
- The pre-push hook (`.githooks/pre-push`) runs ruff + mypy — it must be active: `git config core.hooksPath .githooks`
- If bump-my-version fails due to a dirty tree (e.g. uv.lock not staged), check that the `pre_commit_hooks` in `pyproject.toml` ran correctly
- Never `--skip` the pre-push hook
