"""Entry point — `asher` CLI command and `python -m asher`.

No arguments launches the interactive TUI. A subcommand (``asher status``,
``asher clean``, ``asher night-light auto``, …) runs headlessly — no TUI, no
terminal required — so the robot can be driven from cron, Task Scheduler, or an
SSH session. ``asher --help`` lists the commands; :mod:`asher.headless` owns
what each one does.

``asher watch`` and ``asher update`` are the two subcommands declared here
rather than in :mod:`asher.headless`: that registry is robot actions, each of
which opens a cloud session and exits. ``watch`` manages a long-lived process,
and ``update`` talks to PyPI rather than to a robot, so neither should be made
to authenticate.

``--export`` is kept as a flag alongside the ``export`` subcommand so existing
cron entries keep working unchanged.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from .daemon import ACTIONS as DAEMON_ACTIONS
from .headless import COMMANDS


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="asher",
        description="Terminal dashboard for Litter Robot (LR3/LR4/LR5). "
        "Run with no arguments for the dashboard, or with a command to run headlessly.",
    )
    parser.add_argument(
        "--export",
        nargs="?",
        const="month",
        default=None,
        metavar="[days|month]",
        help="deprecated alias for `asher export` — export activity history to CSV and exit. "
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

    # SUPPRESS keeps an unused subcommand flag from overwriting the top-level one
    # of the same name, so `asher --robot X status` and `asher status --robot X`
    # are equivalent instead of the subparser clobbering it back to None.
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "--robot",
        default=argparse.SUPPRESS,
        metavar="INDEX|NAME",
        help="pick the robot by index or partial name (default: preferred/first).",
    )
    shared.add_argument(
        "--json",
        action="store_true",
        help="print the result as JSON instead of aligned text.",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    # `watch` isn't in the headless registry: that registry is robot actions,
    # each of which opens a cloud session and exits. This one manages a process.
    watch = subparsers.add_parser(
        "watch",
        help="run the notification watcher in the background",
        description="Keep desktop notifications running after this terminal closes. "
        "`start` detaches a watcher process (with a tray icon where one is available), "
        "`run` does the same in the foreground, and `enable` additionally registers it "
        "to start at login (launchd / systemd --user / the Windows registry).",
    )
    watch.add_argument(
        "action",
        nargs="?",
        default="start",
        choices=DAEMON_ACTIONS,
        help="default: start",
    )
    watch.add_argument(
        "--robot",
        default=argparse.SUPPRESS,
        metavar="INDEX|NAME",
        help="pick the robot to watch by index or partial name (default: preferred/first).",
    )
    watch.add_argument(
        "--no-tray",
        action="store_true",
        help="never show a system-tray icon, even where one is available.",
    )

    # Also outside the headless registry: it opens no cloud session, so it must
    # not be made to authenticate just to read a version number.
    update = subparsers.add_parser(
        "update",
        help="check whether a newer release is published",
        description="Check PyPI for a newer asher-cli release and print the command to "
        "install it. Never installs anything itself.",
    )
    update.add_argument(
        "--json",
        action="store_true",
        help="print the result as JSON instead of text.",
    )

    for command in COMMANDS:
        sub = subparsers.add_parser(
            command.name,
            parents=[shared],
            help=command.summary,
            description=f"{command.summary}  (usage: {command.usage})",
        )
        sub.add_argument("args", nargs="*", metavar="ARG", help=f"usage: {command.usage}")
        if command.name == "export":
            sub.add_argument(
                "--output",
                "-o",
                default=argparse.SUPPRESS,
                metavar="PATH",
                help="write to this path instead of ~/Downloads.",
            )
    return parser


def main() -> None:
    args = _build_parser().parse_args()

    if args.command == "watch":
        from .daemon import dispatch  # noqa: PLC0415

        sys.exit(dispatch(args.action, robot=args.robot, tray=not args.no_tray))

    if args.command == "update":
        from .updates import report  # noqa: PLC0415

        up_to_date, message = report(as_json=args.json)
        print(message)
        sys.exit(0 if up_to_date else 10)

    if args.command is not None:
        from .headless import run  # noqa: PLC0415

        sys.exit(
            asyncio.run(
                run(
                    args.command,
                    args.args,
                    robot=args.robot,
                    output=args.output,
                    as_json=getattr(args, "json", False),
                )
            )
        )

    if args.export is not None:
        from .export import _run_headless_export  # noqa: PLC0415

        sys.exit(asyncio.run(_run_headless_export(args)))

    from .app import AsherApp  # noqa: PLC0415

    AsherApp().run()


if __name__ == "__main__":
    main()
