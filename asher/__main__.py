"""Entry point — `asher` CLI command and `python -m asher`.

No flags launches the interactive TUI. ``--export`` runs headlessly (no TUI,
no terminal required) so activity history can be exported from cron, Task
Scheduler, or SSH — see ``asher --export --help``.
"""

from __future__ import annotations

import argparse
import asyncio
import sys


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="asher",
        description="Terminal dashboard for Litter Robot (LR3/LR4/LR5).",
    )
    parser.add_argument(
        "--export",
        nargs="?",
        const="month",
        default=None,
        metavar="[days|month]",
        help="export activity history to CSV and exit (no TUI). "
        "Bare --export = 30 days (Whisker ceiling); --export 7 = last 7 days.",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        metavar="PATH",
        help="with --export: write to this path instead of ~/Downloads.",
    )
    parser.add_argument(
        "--robot",
        default=None,
        metavar="INDEX|NAME",
        help="with --export: pick the robot by index or partial name (default: preferred/first).",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    if args.export is not None:
        from .export import _run_headless_export  # noqa: PLC0415

        sys.exit(asyncio.run(_run_headless_export(args)))

    from .app import AsherApp  # noqa: PLC0415

    AsherApp().run()


if __name__ == "__main__":
    main()
