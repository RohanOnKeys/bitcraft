"""The `bitcraft` command.

    bitcraft                      open BitCraft in a new, large window
    bitcraft run [options]        same, with options
    bitcraft demo                 new window with built-in demo data
    bitcraft here [options]       run inside the current terminal
    bitcraft status               check the API and the last pipeline run
    bitcraft version              print the version

Options for run / here:
    --demo | --api                force a data source (default: auto)
    --api-url URL                 backend to use (default http://localhost:8000)
    --size COLSxROWS              window size for run / demo (default 190x52)
"""

from __future__ import annotations

import argparse
import os
import sys

from bitcraft import __version__
from bitcraft.api_client import DEFAULT_BASE_URL
from bitcraft.launcher import DEFAULT_SIZE, Options, api_healthy, open_window, run_session

COMMANDS = ("run", "demo", "here", "status", "version")


def _size(text: str) -> tuple[int, int]:
    try:
        cols, rows = (int(v) for v in text.lower().split("x"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("size must look like 190x52") from exc
    if cols < 100 or rows < 30:
        raise argparse.ArgumentTypeError("BitCraft needs at least 100x30")
    return cols, rows


def _source_args(p: argparse.ArgumentParser) -> None:
    group = p.add_mutually_exclusive_group()
    group.add_argument("--demo", action="store_true", help="built-in demo data, no API")
    group.add_argument("--api", action="store_true", help="require the API (no demo fallback)")
    p.add_argument(
        "--api-url",
        default=os.environ.get("BITCRAFT_API_URL", DEFAULT_BASE_URL),
        help=f"backend URL (default {DEFAULT_BASE_URL})",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bitcraft",
        description="BitCraft: Bitcoin transaction intelligence in your terminal.",
        epilog="Run `bitcraft` with no arguments to open it in a new window.",
    )
    parser.add_argument("-V", "--version", action="version", version=f"bitcraft {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    run = sub.add_parser("run", help="open in a new, large terminal window (default)")
    _source_args(run)
    run.add_argument("--size", type=_size, default=DEFAULT_SIZE, help="window size, e.g. 190x52")

    demo = sub.add_parser("demo", help="open in a new window with demo data")
    demo.add_argument("--size", type=_size, default=DEFAULT_SIZE, help="window size, e.g. 190x52")

    here = sub.add_parser("here", help="run inside the current terminal")
    _source_args(here)

    status = sub.add_parser("status", help="check the API and the last pipeline run")
    status.add_argument("--api-url", default=os.environ.get("BITCRAFT_API_URL", DEFAULT_BASE_URL))

    sub.add_parser("version", help="print the version")
    return parser


def _options(args: argparse.Namespace) -> Options:
    source = "demo" if getattr(args, "demo", False) else ("api" if getattr(args, "api", False) else "auto")
    return Options(
        source=source,
        api_url=getattr(args, "api_url", DEFAULT_BASE_URL),
        size=getattr(args, "size", DEFAULT_SIZE),
    )


def _launch(opts: Options) -> int:
    try:
        where = open_window(opts)
    except Exception as exc:  # noqa: BLE001 - no GUI terminal: run right here
        print(f"Could not open a new window ({exc}); starting here.")
        return run_session(opts)
    cols, rows = opts.size
    print(f"BitCraft is opening in a new {where} window ({cols}x{rows}).")
    return 0


def _status(api_url: str) -> int:
    print(f"bitcraft {__version__}")
    if not api_healthy(api_url, timeout_s=1.5):
        print(f"API      {api_url}  not reachable (BitCraft will use demo data)")
        return 1
    import httpx

    stats = httpx.get(f"{api_url}/stats/summary", timeout=3).json()
    pipeline = httpx.get(f"{api_url}/pipeline/status", timeout=3).json()
    print(f"API      {api_url}  ok")
    print(f"data     {stats['total_transactions']:,} transactions, {stats['total_alerts']:,} alerts")
    finished = pipeline.get("finished_at") or "-"
    print(f"pipeline {pipeline.get('status', 'unknown')} (finished {finished})")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Bare `bitcraft` (or `bitcraft --demo ...`) means `bitcraft run ...`.
    if not argv or (argv[0] not in COMMANDS and argv[0] not in ("-h", "--help", "-V", "--version")):
        argv.insert(0, "run")
    args = build_parser().parse_args(argv)

    if args.command == "version":
        print(f"bitcraft {__version__}")
        return 0
    if args.command == "status":
        return _status(args.api_url)
    if args.command == "here":
        return run_session(_options(args))
    if args.command == "demo":
        return _launch(Options(source="demo", size=args.size))
    return _launch(_options(args))


if __name__ == "__main__":
    sys.exit(main())
