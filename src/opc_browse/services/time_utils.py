from __future__ import annotations

from datetime import datetime, timezone
import math


def parse_utc_datetime(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_iso_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def normalize_datetime_to_utc_naive_for_mysql(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    aware = to_iso_utc(value)
    return aware.replace(tzinfo=None)


def choose_bucket_seconds(
    start: datetime,
    end: datetime,
    requested_bucket_seconds: int,
    max_points: int,
) -> int:
    if requested_bucket_seconds < 1:
        raise ValueError("requested_bucket_seconds must be >= 1")
    if max_points < 1:
        raise ValueError("max_points must be >= 1")

    duration_seconds = (to_iso_utc(end) - to_iso_utc(start)).total_seconds()
    if duration_seconds <= 0:
        raise ValueError("end must be greater than start")

    minimum_bucket = max(requested_bucket_seconds, math.ceil(duration_seconds / max_points))
    return int(minimum_bucket)
