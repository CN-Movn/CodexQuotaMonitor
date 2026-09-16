"""Command-line entry point for CodexQuotaMonitor."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from scanner import (
    SessionScanner,
    format_reset,
    format_status_line,
    format_updated,
)


def _print_snapshot(scanner: SessionScanner) -> None:
    snapshot = scanner.scan(force=True)
    print(f"sessions_dir={scanner.sessions_dir}")
    print(f"status={format_status_line(snapshot)}")
    print(f"updated_local={format_updated(snapshot.updated_at)}")
    print(f"scanned_files={snapshot.scanned_files}")
    print(f"rate_limit_records={snapshot.rate_limit_records}")
    print(f"malformed_rate_limit_lines={snapshot.malformed_lines}")
    print(f"rate_limit_fields={','.join(snapshot.field_names) or '--'}")
    if snapshot.primary is not None:
        print(
            "5h="
            f"remaining:{snapshot.primary.remaining_percent:g}% "
            f"used:{snapshot.primary.used_percent:g}% "
            f"window_minutes:{snapshot.primary.window_minutes} "
            f"reset_local:{format_reset(snapshot.primary.resets_at)}"
        )
    else:
        print("5h=--")
    if snapshot.weekly is not None:
        print(
            "weekly="
            f"remaining:{snapshot.weekly.remaining_percent:g}% "
            f"used:{snapshot.weekly.used_percent:g}% "
            f"window_minutes:{snapshot.weekly.window_minutes} "
            f"reset_local:{format_reset(snapshot.weekly.resets_at)}"
        )
    else:
        print("weekly=--")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline Codex local quota monitor")
    parser.add_argument(
        "--sessions-dir",
        type=Path,
        default=None,
        help="Override the local Codex sessions directory (mainly for tests).",
    )
    parser.add_argument("--scan", action="store_true", help="Scan once and print the result.")
    parser.add_argument("--smoke-test", action="store_true", help="Create the Windows UI briefly and exit.")
    parser.add_argument("--smoke-seconds", type=float, default=3.0, help="Smoke-test duration.")
    parser.add_argument("--interval", type=float, default=3.0, help="Local file polling interval in seconds.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    scanner = SessionScanner(args.sessions_dir)

    if args.scan:
        _print_snapshot(scanner)
        return 0

    if os.name != "nt":
        print("The tray UI is only supported on Windows.")
        return 2

    from windows_app import WindowsTrayApp

    app = WindowsTrayApp(
        scanner,
        refresh_interval=args.interval,
    )
    return app.run(smoke_seconds=args.smoke_seconds if args.smoke_test else None)


if __name__ == "__main__":
    raise SystemExit(main())
