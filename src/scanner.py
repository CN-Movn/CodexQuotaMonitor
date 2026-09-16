"""Read-only scanner for Codex session JSONL rate limit records."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PRIMARY_WINDOW_MINUTES = 300
WEEKLY_WINDOW_MINUTES = 7 * 24 * 60


@dataclass(frozen=True)
class RateLimitWindow:
    """One observed Codex rate-limit window."""

    key: str
    used_percent: float
    remaining_percent: float
    window_minutes: int | None
    resets_at: int | None
    observed_at: datetime
    source_file: Path
    line_number: int


@dataclass(frozen=True)
class QuotaSnapshot:
    """Latest usable values found in the local session logs."""

    primary: RateLimitWindow | None
    weekly: RateLimitWindow | None
    updated_at: datetime | None
    scanned_files: int
    rate_limit_records: int
    malformed_lines: int
    field_names: tuple[str, ...]

    @property
    def has_data(self) -> bool:
        return self.primary is not None or self.weekly is not None


def default_codex_root() -> Path:
    """Return the current user's Codex data root without reading credentials."""

    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        return Path(user_profile) / ".codex"
    return Path.home() / ".codex"


def default_sessions_dir() -> Path:
    return default_codex_root() / "sessions"


def _as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _as_int(value: Any) -> int | None:
    number = _as_float(value)
    if number is None:
        return None
    return int(number)


def _parse_timestamp(value: Any, fallback: datetime) -> datetime:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            pass
    return fallback.astimezone(timezone.utc)


def _parse_reset(value: Any) -> int | None:
    reset = _as_int(value)
    if reset is None:
        return None
    # Be tolerant of a future version emitting milliseconds instead of seconds.
    if reset > 100_000_000_000:
        reset //= 1000
    return reset


def _find_rate_limits(record: Any) -> dict[str, Any] | None:
    """Find the known rate_limits container without traversing message text."""

    if not isinstance(record, dict):
        return None

    candidates: list[Any] = [record]
    for key in ("payload", "data", "response", "result"):
        value = record.get(key)
        if isinstance(value, dict):
            candidates.append(value)

    for candidate in candidates:
        value = candidate.get("rate_limits")
        if isinstance(value, dict):
            return value
    return None


def _window_kind(field_name: str, value: dict[str, Any]) -> str | None:
    minutes = _as_int(value.get("window_minutes"))
    if minutes == PRIMARY_WINDOW_MINUTES:
        return "primary"
    if minutes == WEEKLY_WINDOW_MINUTES:
        return "weekly"

    # Older/future records may omit window_minutes but keep the semantic key.
    normalized = field_name.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in {"primary", "five_hour", "5h", "five_hours"}:
        return "primary"
    if normalized in {"secondary", "weekly", "week", "seven_day", "7d"}:
        return "weekly"
    return None


def _iter_windows(rate_limits: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    seen: set[str] = set()
    for field_name in ("primary", "secondary", "weekly", "five_hour", "seven_day"):
        value = rate_limits.get(field_name)
        if isinstance(value, dict):
            seen.add(field_name)
            yield field_name, value
    for field_name, value in rate_limits.items():
        if field_name not in seen and isinstance(value, dict):
            yield str(field_name), value


class SessionScanner:
    """Incrementally scan Codex session JSONL files using only local file I/O."""

    def __init__(self, sessions_dir: Path | None = None) -> None:
        self.sessions_dir = Path(sessions_dir or default_sessions_dir())
        self._signature: tuple[tuple[str, int, int], ...] | None = None
        self._cached_snapshot: QuotaSnapshot | None = None

    def _files_and_signature(self) -> tuple[list[Path], tuple[tuple[str, int, int], ...]]:
        if not self.sessions_dir.is_dir():
            return [], ()

        files: list[Path] = []
        for path in self.sessions_dir.rglob("*.jsonl"):
            if not path.is_file():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            files.append(path)

        files.sort(key=lambda item: str(item).lower())
        signature = tuple(
            (str(path), path.stat().st_mtime_ns, path.stat().st_size)
            for path in files
            if path.exists()
        )
        return files, signature

    def scan(self, *, force: bool = False) -> QuotaSnapshot:
        files, signature = self._files_and_signature()
        if not force and self._signature == signature and self._cached_snapshot is not None:
            return self._cached_snapshot

        latest: dict[str, tuple[tuple[float, int, int], RateLimitWindow]] = {}
        file_mtimes: dict[Path, int] = {}
        field_names: set[str] = set()
        malformed_lines = 0
        rate_limit_records = 0

        for path in files:
            try:
                file_stat = path.stat()
                file_mtimes[path] = file_stat.st_mtime_ns
                fallback_time = datetime.fromtimestamp(file_stat.st_mtime, timezone.utc)
                handle = path.open("r", encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                continue

            with handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip() or "rate_limits" not in line.lower():
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        # Codex can be writing the final line while this pass reads it.
                        malformed_lines += 1
                        continue

                    rate_limits = _find_rate_limits(record)
                    if rate_limits is None:
                        continue
                    rate_limit_records += 1
                    field_names.update(str(key) for key in rate_limits.keys())

                    if isinstance(record, dict):
                        observed_at = _parse_timestamp(record.get("timestamp"), fallback_time)
                    else:
                        observed_at = fallback_time
                    record_key = (
                        observed_at.timestamp(),
                        file_mtimes.get(path, 0),
                        line_number,
                    )

                    for field_name, value in _iter_windows(rate_limits):
                        kind = _window_kind(field_name, value)
                        used = _as_float(value.get("used_percent"))
                        if kind is None or used is None:
                            continue

                        used = max(0.0, min(100.0, used))
                        window = RateLimitWindow(
                            key=kind,
                            used_percent=used,
                            remaining_percent=100.0 - used,
                            window_minutes=_as_int(value.get("window_minutes")),
                            resets_at=_parse_reset(value.get("resets_at")),
                            observed_at=observed_at,
                            source_file=path,
                            line_number=line_number,
                        )
                        previous = latest.get(kind)
                        if previous is None or record_key >= previous[0]:
                            latest[kind] = (record_key, window)

        primary = latest.get("primary", (None, None))[1]
        weekly = latest.get("weekly", (None, None))[1]
        observed_times = [window.observed_at for window in (primary, weekly) if window is not None]
        snapshot = QuotaSnapshot(
            primary=primary,
            weekly=weekly,
            updated_at=max(observed_times) if observed_times else None,
            scanned_files=len(files),
            rate_limit_records=rate_limit_records,
            malformed_lines=malformed_lines,
            field_names=tuple(sorted(field_names)),
        )
        self._signature = signature
        self._cached_snapshot = snapshot
        return snapshot


def _format_percent(value: float | None) -> str:
    if value is None:
        return "--"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.1f}".rstrip("0").rstrip(".")


def format_reset(reset_at: int | None) -> str:
    if reset_at is None:
        return "--"
    try:
        value = datetime.fromtimestamp(reset_at, timezone.utc).astimezone()
    except (OverflowError, OSError, ValueError):
        return "--"
    return value.strftime("%m-%d %H:%M")


def format_updated(updated_at: datetime | None) -> str:
    if updated_at is None:
        return "--"
    return updated_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")


def format_status_line(snapshot: QuotaSnapshot) -> str:
    primary = _format_percent(snapshot.primary.remaining_percent if snapshot.primary else None)
    weekly = _format_percent(snapshot.weekly.remaining_percent if snapshot.weekly else None)
    return f"Codex  5H {primary}% | W {weekly}%"


def format_tooltip(snapshot: QuotaSnapshot) -> str:
    if not snapshot.has_data:
        return f"{format_status_line(snapshot)} | no local rate-limit record"

    parts = [format_status_line(snapshot)]
    if snapshot.primary is not None:
        parts.append(
            f"5H left {_format_percent(snapshot.primary.remaining_percent)}% "
            f"(used {_format_percent(snapshot.primary.used_percent)}%, reset {format_reset(snapshot.primary.resets_at)})"
        )
    else:
        parts.append("5H left --")
    if snapshot.weekly is not None:
        parts.append(
            f"W left {_format_percent(snapshot.weekly.remaining_percent)}% "
            f"(used {_format_percent(snapshot.weekly.used_percent)}%, reset {format_reset(snapshot.weekly.resets_at)})"
        )
    else:
        parts.append("W left --")
    parts.append(f"updated {format_updated(snapshot.updated_at)}")
    return " | ".join(parts)
