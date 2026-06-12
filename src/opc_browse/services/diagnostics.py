from __future__ import annotations

from typing import Any


def summarize_skipped(skipped_items: list[dict[str, Any]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for item in skipped_items:
        reason = str(item.get("reason") or "unknown")
        summary[reason] = summary.get(reason, 0) + 1
    return summary


def classify_tag_profile_flags(profile_stats: dict[str, Any]) -> dict[str, bool]:
    sample_count = int(profile_stats.get("sample_count") or 0)
    numeric_sample_count = int(profile_stats.get("numeric_sample_count") or 0)
    null_numeric_count = int(profile_stats.get("null_numeric_count") or 0)
    error_count = int(profile_stats.get("error_count") or 0)
    distinct_numeric_count = int(profile_stats.get("distinct_numeric_count") or 0)

    return {
        "has_numeric_data": numeric_sample_count > 0,
        "mostly_null_numeric": sample_count > 0 and null_numeric_count / sample_count >= 0.8,
        "appears_constant": numeric_sample_count > 1 and distinct_numeric_count <= 1,
        "has_errors": error_count > 0,
        "enough_samples": sample_count >= 30,
    }


def format_float(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}"


def safe_percent(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator
