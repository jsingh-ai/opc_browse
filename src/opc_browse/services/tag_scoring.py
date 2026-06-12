from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


SEMANTIC_TYPES = {
    "continuous_numeric",
    "counter_like",
    "state_like_numeric",
    "constant",
    "sparse",
    "text_or_state",
    "unknown",
}


def _int_value(stats: dict[str, Any], key: str) -> int:
    return int(stats.get(key) or 0)


def _float_value(stats: dict[str, Any], key: str) -> float | None:
    value = stats.get(key)
    if value is None:
        return None
    return float(value)


def coefficient_of_variation(avg_value, stddev_value) -> float | None:
    if avg_value is None or stddev_value is None:
        return None
    average = float(avg_value)
    stddev = float(stddev_value)
    if average == 0:
        return None
    return abs(stddev / average)


def classify_constant(stats: dict[str, Any]) -> bool:
    numeric_sample_count = _int_value(stats, "numeric_sample_count")
    distinct_numeric_count = _int_value(stats, "distinct_numeric_count")
    min_value = _float_value(stats, "min_value")
    max_value = _float_value(stats, "max_value")
    stddev_value = _float_value(stats, "stddev_value")

    if numeric_sample_count < 3:
        return False
    if distinct_numeric_count > 0 and distinct_numeric_count <= 1:
        return True
    if min_value is not None and max_value is not None and min_value == max_value:
        return True
    if stddev_value is not None and stddev_value <= 1e-12:
        return True
    return False


def classify_sparse(stats: dict[str, Any]) -> bool:
    sample_count = _int_value(stats, "sample_count")
    numeric_sample_count = _int_value(stats, "numeric_sample_count")
    null_numeric_count = _int_value(stats, "null_numeric_count")

    if sample_count <= 0:
        return True
    if numeric_sample_count <= 0:
        return True
    if null_numeric_count / sample_count >= 0.8:
        return True
    if numeric_sample_count / sample_count < 0.2:
        return True
    return False


def classify_counter_like(stats: dict[str, Any]) -> bool:
    numeric_sample_count = _int_value(stats, "numeric_sample_count")
    distinct_numeric_count = _int_value(stats, "distinct_numeric_count")
    min_value = _float_value(stats, "min_value")
    max_value = _float_value(stats, "max_value")
    stddev_value = _float_value(stats, "stddev_value")

    if numeric_sample_count < 10 or classify_constant(stats):
        return False
    if min_value is None or max_value is None:
        return False
    if min_value < 0 or max_value <= min_value:
        return False
    if distinct_numeric_count < 5:
        return False
    if stddev_value is not None and stddev_value <= 0:
        return False
    return True


def classify_state_like_numeric(stats: dict[str, Any]) -> bool:
    numeric_sample_count = _int_value(stats, "numeric_sample_count")
    distinct_numeric_count = _int_value(stats, "distinct_numeric_count")
    min_value = _float_value(stats, "min_value")
    max_value = _float_value(stats, "max_value")
    data_type = str(stats.get("data_type") or "").lower()

    if numeric_sample_count < 5 or classify_constant(stats):
        return False
    if distinct_numeric_count < 2 or distinct_numeric_count > 12:
        return False
    if min_value is not None and max_value is not None and (max_value - min_value) > 20:
        return False
    if any(token in data_type for token in ("bool", "byte", "short", "int", "uint")):
        return True
    return distinct_numeric_count <= 8


def classify_stale(
    last_seen_utc,
    now_utc,
    stale_hours: int = 24,
) -> bool:
    if last_seen_utc is None:
        return True

    reference = now_utc
    if reference is None:
        reference = datetime.now(timezone.utc)

    if isinstance(last_seen_utc, str):
        last_seen = datetime.fromisoformat(last_seen_utc.replace("Z", "+00:00"))
    else:
        last_seen = last_seen_utc
    if isinstance(reference, str):
        reference = datetime.fromisoformat(reference.replace("Z", "+00:00"))

    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)

    return (reference - last_seen).total_seconds() > stale_hours * 3600


def infer_semantic_type(stats: dict[str, Any]) -> str:
    numeric_sample_count = _int_value(stats, "numeric_sample_count")
    text_sample_count = _int_value(stats, "text_sample_count")

    if text_sample_count > numeric_sample_count and text_sample_count > 0:
        return "text_or_state"
    if classify_constant(stats):
        return "constant"
    if classify_sparse(stats):
        return "sparse"
    if classify_counter_like(stats):
        return "counter_like"
    if classify_state_like_numeric(stats):
        return "state_like_numeric"
    if numeric_sample_count > 0:
        return "continuous_numeric"
    return "unknown"


def score_tag_usefulness(stats: dict[str, Any]) -> dict[str, Any]:
    sample_count = _int_value(stats, "sample_count")
    numeric_sample_count = _int_value(stats, "numeric_sample_count")
    null_numeric_count = _int_value(stats, "null_numeric_count")
    error_count = _int_value(stats, "error_count")
    quality_good_count = _int_value(stats, "quality_good_count")
    quality_bad_count = _int_value(stats, "quality_bad_count")
    semantic_type = infer_semantic_type(stats)
    stale = classify_stale(stats.get("last_seen_utc"), stats.get("now_utc"))
    sparse = classify_sparse(stats)
    constant = classify_constant(stats)
    changing = not constant and _int_value(stats, "distinct_numeric_count") > 1
    mostly_null = sample_count > 0 and (null_numeric_count / sample_count) >= 0.8

    score = 0
    reasons: list[str] = []
    badges: list[str] = []

    if numeric_sample_count > 0:
        score += 25
        reasons.append("has numeric data")
        badges.append("numeric")
    else:
        reasons.append("no numeric samples")

    if sample_count >= 100:
        score += 20
        reasons.append("strong sample count")
        badges.append("high-sample")
    elif sample_count >= 30:
        score += 10
        reasons.append("enough samples")
    else:
        score -= 15
        reasons.append("low sample count")
        badges.append("low-sample")

    if not stale:
        score += 15
        reasons.append("recently active")
        badges.append("recent")
    else:
        score -= 20
        reasons.append("stale")
        badges.append("stale")

    if changing:
        score += 20
        reasons.append("value changes over time")
        badges.append("changing")

    if constant:
        score -= 30
        reasons.append("appears constant")
        badges.append("constant")

    if sparse:
        score -= 20
        reasons.append("sparse or mostly missing")
        badges.append("sparse")

    if mostly_null:
        score -= 15
        reasons.append("mostly null numeric values")

    if error_count > 0:
        if sample_count > 0 and (error_count / sample_count) >= 0.2:
            score -= 20
            reasons.append("many errors")
        else:
            score -= 8
            reasons.append("has some errors")
        badges.append("errors")

    if quality_good_count or quality_bad_count:
        total_quality = quality_good_count + quality_bad_count
        if total_quality > 0:
            good_rate = quality_good_count / total_quality
            if good_rate >= 0.9:
                score += 10
                reasons.append("good quality rate")
                badges.append("good-quality")
            elif good_rate < 0.5:
                score -= 15
                reasons.append("poor quality rate")
                badges.append("poor-quality")

    if semantic_type == "counter_like":
        score += 8
        reasons.append("looks like a counter")
        badges.append("counter")
    elif semantic_type == "state_like_numeric":
        score += 5
        reasons.append("looks like a numeric state")
        badges.append("state-like")
    elif semantic_type == "text_or_state":
        score -= 10
        reasons.append("mostly text or state data")
        badges.append("text")
    elif semantic_type == "unknown":
        score -= 5
        reasons.append("unknown semantic type")

    score = max(0, min(100, score))
    if score >= 75:
        grade = "high"
    elif score >= 50:
        grade = "medium"
    elif score >= 25:
        grade = "low"
    else:
        grade = "ignore"

    ordered_badges = list(dict.fromkeys([semantic_type, *badges]))
    ordered_reasons = list(dict.fromkeys(reasons))
    return {
        "score": score,
        "grade": grade,
        "semantic_type": semantic_type,
        "reasons": ordered_reasons,
        "badges": ordered_badges,
    }
