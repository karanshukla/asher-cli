"""The subpackage import rules from CLAUDE.md, checked against the source."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).parent.parent / "asher"

FORBIDDEN = {
    "core": {"tui", "desktop", "mcp", "headless"},
    "robot": {"tui", "desktop", "mcp", "headless"},
    "mcp": {"tui", "desktop", "headless"},
    "desktop": {"tui"},
}


def _imported_layers(path: Path) -> set[str]:
    module_parts = path.relative_to(PACKAGE.parent).with_suffix("").parts
    package = module_parts[:-1]
    layers = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[: len(package) - node.level + 1]
                target = [*base, *(node.module.split(".") if node.module else [])]
                names = (
                    [target + [alias.name] for alias in node.names] if not node.module else [target]
                )
            else:
                names = [(node.module or "").split(".")]
        elif isinstance(node, ast.Import):
            names = [alias.name.split(".") for alias in node.names]
        else:
            continue
        layers.update(parts[1] for parts in names if len(parts) > 1 and parts[0] == "asher")
    return layers


@pytest.mark.parametrize("layer", sorted(FORBIDDEN))
def test_layer_imports_stay_inside_their_boundary(layer: str) -> None:
    violations = {
        str(path.relative_to(PACKAGE.parent)): sorted(_imported_layers(path) & FORBIDDEN[layer])
        for path in (PACKAGE / layer).rglob("*.py")
    }
    assert {path: bad for path, bad in violations.items() if bad} == {}


def test_only_the_entry_point_reaches_into_the_tui() -> None:
    importers = {
        str(path.relative_to(PACKAGE.parent))
        for path in PACKAGE.rglob("*.py")
        if "tui" not in path.relative_to(PACKAGE).parts[:1] and "tui" in _imported_layers(path)
    }
    assert importers == {"asher/__main__.py"}
