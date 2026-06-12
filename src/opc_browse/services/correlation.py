from __future__ import annotations

import math
from typing import Any

import numpy as np


VARIANCE_EPSILON = 1e-12
SKIP_REASON_TARGET_INSUFFICIENT_DATA = "target_insufficient_data"
SKIP_REASON_CANDIDATE_INSUFFICIENT_OVERLAP = "candidate_insufficient_overlap"
SKIP_REASON_CONSTANT_OR_INSUFFICIENT_VARIANCE = "constant_or_insufficient_variance"
SKIP_REASON_INSUFFICIENT_PAIR_COUNT = "insufficient_pair_count"
SKIP_REASON_NON_NUMERIC_OR_MISSING_SERIES = "non_numeric_or_missing_series"
SKIP_REASON_ANALYSIS_ERROR = "analysis_error"


def _coerce_float(value: Any) -> float:
    if value is None:
        return float("nan")
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _to_float_array(values: list[Any]) -> np.ndarray:
    return np.asarray([_coerce_float(value) for value in values], dtype=float)


def _pearson_corr_with_count(
    x: list[Any],
    y: list[Any],
    min_pair_count: int,
) -> tuple[float | None, int]:
    x_arr = _to_float_array(x)
    y_arr = _to_float_array(y)
    mask = np.isfinite(x_arr) & np.isfinite(y_arr)
    x_valid = x_arr[mask]
    y_valid = y_arr[mask]
    pair_count = int(mask.sum())

    if pair_count < min_pair_count:
        return None, pair_count
    if np.std(x_valid) <= VARIANCE_EPSILON or np.std(y_valid) <= VARIANCE_EPSILON:
        return None, pair_count

    corr = float(np.corrcoef(x_valid, y_valid)[0, 1])
    if not math.isfinite(corr):
        return None, pair_count
    return corr, pair_count


def _finite_count_and_std(values: list[Any]) -> tuple[int, float | None]:
    arr = _to_float_array(values)
    finite = arr[np.isfinite(arr)]
    if len(finite) == 0:
        return 0, None
    return int(len(finite)), float(np.std(finite))


def is_target_series_usable(
    target_series: dict[int, float],
    min_pair_count: int,
) -> bool:
    target_values_only = list(target_series.values())
    target_finite_count, target_stddev = _finite_count_and_std(target_values_only)
    if target_finite_count < min_pair_count or target_stddev is None:
        return False
    if target_stddev <= VARIANCE_EPSILON:
        return False
    return True


def pearson_corr(x: list[Any], y: list[Any], min_pair_count: int) -> float | None:
    corr, _ = _pearson_corr_with_count(x, y, min_pair_count)
    return corr


def first_difference(values: list[Any]) -> list[float | None]:
    if len(values) < 2:
        return []

    diffs: list[float | None] = []
    for previous, current in zip(values, values[1:]):
        prev_value = _coerce_float(previous)
        curr_value = _coerce_float(current)
        if not math.isfinite(prev_value) or not math.isfinite(curr_value):
            diffs.append(None)
        else:
            diffs.append(curr_value - prev_value)
    return diffs


def best_lagged_corr(
    target_values: list[Any],
    candidate_values: list[Any],
    max_lag_buckets: int,
    min_pair_count: int,
) -> tuple[float | None, int, int]:
    if len(target_values) != len(candidate_values):
        raise ValueError("target_values and candidate_values must have the same length")

    best_corr: float | None = None
    best_lag = 0
    best_pair_count = 0

    for lag in range(-max_lag_buckets, max_lag_buckets + 1):
        if lag > 0:
            target_slice = target_values[lag:]
            candidate_slice = candidate_values[:-lag]
        elif lag < 0:
            offset = -lag
            target_slice = target_values[:-offset]
            candidate_slice = candidate_values[offset:]
        else:
            target_slice = target_values
            candidate_slice = candidate_values

        corr, pair_count = _pearson_corr_with_count(
            target_slice,
            candidate_slice,
            min_pair_count=min_pair_count,
        )
        if corr is None:
            continue
        if best_corr is None or abs(corr) > abs(best_corr) or (
            abs(corr) == abs(best_corr) and abs(lag) < abs(best_lag)
        ):
            best_corr = corr
            best_lag = lag
            best_pair_count = pair_count

    return best_corr, best_lag, best_pair_count


def classify_relationship(
    same_time_corr: float | None,
    delta_corr: float | None,
    best_lag_corr: float | None,
    best_lag_buckets: int,
    bucket_seconds: int,
) -> dict[str, Any]:
    same_abs = abs(same_time_corr) if same_time_corr is not None else -1.0
    delta_abs = abs(delta_corr) if delta_corr is not None else -1.0
    lag_abs = abs(best_lag_corr) if best_lag_corr is not None else -1.0

    dominant_value = same_time_corr if same_time_corr is not None else 0.0
    relationship_type = "moves_together"
    notes: list[str] = []

    if best_lag_buckets != 0 and best_lag_corr is not None and lag_abs >= max(same_abs, delta_abs, 0.5):
        if best_lag_buckets > 0:
            relationship_type = "possible_driver"
            notes.append(
                f"candidate leads target by {best_lag_buckets * bucket_seconds} seconds"
            )
        else:
            relationship_type = "possible_effect"
            notes.append(
                f"candidate follows target by {abs(best_lag_buckets * bucket_seconds)} seconds"
            )
        notes.append("strongest relationship came from lagged correlation")
        dominant_value = best_lag_corr
    elif delta_corr is not None and delta_abs >= max(same_abs, lag_abs, 0.5):
        relationship_type = "changes_together"
        notes.append("candidate changes align with target changes")
        dominant_value = delta_corr
    else:
        notes.append("candidate moves at the same time as target")
        dominant_value = same_time_corr if same_time_corr is not None else dominant_value

    if dominant_value < 0:
        notes.append("relationship is inverse")

    return {
        "relationship_type": relationship_type,
        "score": max(same_abs, delta_abs, lag_abs, 0.0),
        "direction": "positive" if dominant_value >= 0 else "negative",
        "best_lag_seconds": best_lag_buckets * bucket_seconds,
        "notes": notes,
    }


def _align_series_to_dense_lists(
    target_series: dict[int, float],
    candidate_series: dict[int, float],
) -> tuple[list[float | None], list[float | None]]:
    if not target_series and not candidate_series:
        return [], []

    all_indices = list(target_series.keys()) + list(candidate_series.keys())
    start_index = min(all_indices)
    end_index = max(all_indices)
    target_values: list[float | None] = []
    candidate_values: list[float | None] = []

    for bucket_index in range(start_index, end_index + 1):
        target_values.append(target_series.get(bucket_index))
        candidate_values.append(candidate_series.get(bucket_index))

    return target_values, candidate_values


def analyze_relationships(
    target_series: dict[int, float],
    candidate_series_by_tag_id: dict[int, dict[int, float]],
    metadata_by_tag_id: dict[int, dict[str, Any]],
    bucket_seconds: int,
    min_pair_count: int,
    max_lag_seconds: int,
    max_results: int,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    max_lag_buckets = max_lag_seconds // bucket_seconds if bucket_seconds > 0 else 0
    if not is_target_series_usable(target_series, min_pair_count):
        for tag_id in candidate_series_by_tag_id:
            skipped.append({"tag_id": tag_id, "reason": SKIP_REASON_TARGET_INSUFFICIENT_DATA})
        return {
            "results": [],
            "skipped": skipped,
            "analyzed_count": 0,
        }

    for tag_id, candidate_series in candidate_series_by_tag_id.items():
        metadata = metadata_by_tag_id.get(tag_id, {})
        if not candidate_series:
            skipped.append({"tag_id": tag_id, "reason": SKIP_REASON_NON_NUMERIC_OR_MISSING_SERIES})
            continue

        target_values, candidate_values = _align_series_to_dense_lists(
            target_series,
            candidate_series,
        )
        candidate_finite_count, candidate_stddev = _finite_count_and_std(candidate_values)
        if candidate_finite_count == 0 or candidate_stddev is None:
            skipped.append({"tag_id": tag_id, "reason": SKIP_REASON_NON_NUMERIC_OR_MISSING_SERIES})
            continue
        if candidate_stddev <= VARIANCE_EPSILON:
            skipped.append(
                {"tag_id": tag_id, "reason": SKIP_REASON_CONSTANT_OR_INSUFFICIENT_VARIANCE}
            )
            continue

        overlap_count = int(
            np.sum(
                np.isfinite(_to_float_array(target_values))
                & np.isfinite(_to_float_array(candidate_values))
            )
        )
        if overlap_count == 0:
            skipped.append(
                {"tag_id": tag_id, "reason": SKIP_REASON_CANDIDATE_INSUFFICIENT_OVERLAP}
            )
            continue

        try:
            same_time_corr, same_pair_count = _pearson_corr_with_count(
                target_values,
                candidate_values,
                min_pair_count=min_pair_count,
            )
            delta_corr, delta_pair_count = _pearson_corr_with_count(
                first_difference(target_values),
                first_difference(candidate_values),
                min_pair_count=min_pair_count,
            )
            best_lag_corr, best_lag_buckets, lag_pair_count = best_lagged_corr(
                target_values,
                candidate_values,
                max_lag_buckets=max_lag_buckets,
                min_pair_count=min_pair_count,
            )
        except Exception:
            skipped.append({"tag_id": tag_id, "reason": SKIP_REASON_ANALYSIS_ERROR})
            continue

        if same_time_corr is None and delta_corr is None and best_lag_corr is None:
            if overlap_count < min_pair_count:
                reason = SKIP_REASON_CANDIDATE_INSUFFICIENT_OVERLAP
            elif max(same_pair_count, delta_pair_count, lag_pair_count) < min_pair_count:
                reason = SKIP_REASON_INSUFFICIENT_PAIR_COUNT
            else:
                reason = SKIP_REASON_ANALYSIS_ERROR
            skipped.append({"tag_id": tag_id, "reason": reason})
            continue

        relationship = classify_relationship(
            same_time_corr=same_time_corr,
            delta_corr=delta_corr,
            best_lag_corr=best_lag_corr,
            best_lag_buckets=best_lag_buckets,
            bucket_seconds=bucket_seconds,
        )

        pair_count = max(same_pair_count, delta_pair_count, lag_pair_count)
        results.append(
            {
                "machine_id": metadata.get("machine_id"),
                "tag_id": tag_id,
                "label": metadata.get("label")
                or metadata.get("display_name")
                or metadata.get("browse_name")
                or metadata.get("opc_path"),
                "opc_path": metadata.get("opc_path"),
                "display_name": metadata.get("display_name"),
                "data_type": metadata.get("data_type"),
                "same_time_corr": same_time_corr,
                "delta_corr": delta_corr,
                "best_lag_corr": best_lag_corr,
                "best_lag_seconds": relationship["best_lag_seconds"],
                "pair_count": pair_count,
                "relationship_type": relationship["relationship_type"],
                "score": relationship["score"],
                "direction": relationship["direction"],
                "notes": relationship["notes"],
            }
        )

    results.sort(key=lambda item: (-item["score"], -item["pair_count"], item["tag_id"]))
    skipped.sort(key=lambda item: item["tag_id"])

    return {
        "results": results[:max_results],
        "skipped": skipped,
        "analyzed_count": len(results),
    }
