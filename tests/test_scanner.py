from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.scanner import (
    SessionScanner,
    format_status_line,
    format_tooltip,
)


def _record(timestamp: str, *, primary: float | None = 45.0, weekly: float | None = 20.0) -> dict:
    rate_limits: dict = {
        "limit_id": "codex",
        "limit_name": None,
        "credits": {"has_credits": False, "unlimited": False, "balance": "0"},
        "plan_type": "plus",
        "individual_limit": None,
        "spend_control_reached": None,
        "rate_limit_reached_type": None,
    }
    if primary is not None:
        rate_limits["primary"] = {
            "used_percent": primary,
            "window_minutes": 300,
            "resets_at": 1789470342,
        }
    if weekly is not None:
        rate_limits["secondary"] = {
            "used_percent": weekly,
            "window_minutes": 10080,
            "resets_at": 1789953273,
        }
    return {
        "timestamp": timestamp,
        "ordinal": 1,
        "type": "event_msg",
        "payload": {"type": "token_count", "rate_limits": rate_limits},
    }


class SessionScannerTests(unittest.TestCase):
    def test_reads_real_payload_shape_and_computes_remaining(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "2026" / "09" / "session.jsonl"
            path.parent.mkdir(parents=True)
            path.write_text(
                "not-json-without-rate-limits\n"
                + json.dumps(_record("2026-09-15T09:18:00.000Z"))
                + "\n",
                encoding="utf-8",
            )

            snapshot = SessionScanner(path.parent).scan(force=True)

            self.assertIsNotNone(snapshot.primary)
            self.assertIsNotNone(snapshot.weekly)
            assert snapshot.primary is not None
            assert snapshot.weekly is not None
            self.assertEqual(snapshot.primary.remaining_percent, 55.0)
            self.assertEqual(snapshot.weekly.remaining_percent, 80.0)
            self.assertEqual(snapshot.primary.window_minutes, 300)
            self.assertEqual(snapshot.weekly.window_minutes, 10080)
            self.assertIn("credits", snapshot.field_names)
            self.assertIn("primary", snapshot.field_names)
            self.assertIn("secondary", snapshot.field_names)
            self.assertTrue(format_tooltip(snapshot).startswith("Codex  5H 55% | W 80%"))

    def test_skips_malformed_tail_and_keeps_latest_valid_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "session.jsonl"
            path.write_text(
                json.dumps(_record("2026-09-15T09:10:00.000Z", primary=30.0))
                + "\n"
                + json.dumps(_record("2026-09-15T09:11:00.000Z", primary=40.0, weekly=None))
                + "\n"
                + '{"timestamp":"2026-09-15T09:12:00.000Z","payload":{"rate_limits":',
                encoding="utf-8",
            )

            snapshot = SessionScanner(Path(temp_dir)).scan(force=True)

            self.assertEqual(snapshot.primary.used_percent, 40.0)
            self.assertEqual(snapshot.weekly.used_percent, 20.0)
            self.assertEqual(snapshot.malformed_lines, 1)

    def test_matches_windows_by_window_length_and_supports_top_level_container(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "session.jsonl"
            record = {
                "timestamp": "2026-09-15T09:20:00.000Z",
                "rate_limits": {
                    "first": {"used_percent": 10, "window_minutes": 10080},
                    "second": {"used_percent": 25, "window_minutes": 300},
                },
            }
            path.write_text(json.dumps(record) + "\n", encoding="utf-8")

            snapshot = SessionScanner(Path(temp_dir)).scan(force=True)

            self.assertEqual(snapshot.primary.used_percent, 25.0)
            self.assertEqual(snapshot.weekly.used_percent, 10.0)

    def test_no_records_is_a_valid_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "session.jsonl"
            path.write_text(json.dumps({"type": "message", "payload": {}}) + "\n", encoding="utf-8")

            snapshot = SessionScanner(Path(temp_dir)).scan(force=True)

            self.assertFalse(snapshot.has_data)
            self.assertIsNone(snapshot.updated_at)
            self.assertEqual(format_status_line(snapshot), "Codex  5H --% | W --%")
            self.assertIn("no local rate-limit record", format_tooltip(snapshot))

    def test_signature_cache_refreshes_after_file_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "session.jsonl"
            path.write_text(json.dumps(_record("2026-09-15T09:10:00.000Z", primary=30.0)) + "\n", encoding="utf-8")
            scanner = SessionScanner(Path(temp_dir))

            first = scanner.scan()
            cached = scanner.scan()
            self.assertIs(first, cached)

            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(_record("2026-09-15T09:11:00.000Z", primary=35.0)) + "\n")

            second = scanner.scan()
            self.assertIsNot(first, second)
            self.assertEqual(second.primary.used_percent, 35.0)


if __name__ == "__main__":
    unittest.main()
