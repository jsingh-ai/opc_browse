from datetime import datetime, timezone

import pytest

from opc_browse.services.time_utils import (
    choose_bucket_seconds,
    normalize_datetime_to_utc_naive_for_mysql,
    parse_utc_datetime,
    to_iso_utc,
)


def test_parse_utc_datetime_handles_z_suffix():
    result = parse_utc_datetime("2026-06-11T00:00:00Z")
    assert result == datetime(2026, 6, 11, 0, 0, 0, tzinfo=timezone.utc)


def test_to_iso_utc_adds_utc_to_naive_datetime():
    result = to_iso_utc(datetime(2026, 6, 11, 0, 0, 0))
    assert result.tzinfo == timezone.utc


def test_normalize_datetime_to_utc_naive_for_mysql_returns_naive_utc():
    dt = datetime(2026, 6, 11, 0, 0, 0, tzinfo=timezone.utc)
    result = normalize_datetime_to_utc_naive_for_mysql(dt)
    assert result == datetime(2026, 6, 11, 0, 0, 0)
    assert result.tzinfo is None


def test_choose_bucket_seconds_keeps_requested_when_under_limit():
    start = datetime(2026, 6, 11, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 6, 11, 1, 0, 0, tzinfo=timezone.utc)
    assert choose_bucket_seconds(start, end, 60, 120) == 60


def test_choose_bucket_seconds_increases_to_fit_max_points():
    start = datetime(2026, 6, 11, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 6, 12, 0, 0, 0, tzinfo=timezone.utc)
    assert choose_bucket_seconds(start, end, 60, 1000) == 87


def test_choose_bucket_seconds_does_not_increase_when_within_max_points():
    start = datetime(2026, 6, 11, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 6, 11, 0, 30, 0, tzinfo=timezone.utc)
    assert choose_bucket_seconds(start, end, 60, 1000) == 60


def test_choose_bucket_seconds_rejects_invalid_range():
    start = datetime(2026, 6, 11, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 6, 11, 0, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        choose_bucket_seconds(start, end, 60, 100)
