from __future__ import annotations

from typing import Any

from opc_browse.models import RelationshipRequest
from opc_browse.services.correlation import (
    SKIP_REASON_TARGET_INSUFFICIENT_DATA,
    analyze_relationships,
    is_target_series_usable,
)
from opc_browse.services.diagnostics import summarize_skipped
from opc_browse.services.relationship_queries import (
    fetch_bucketed_numeric_series,
    fetch_candidate_numeric_tags,
    fetch_target_tag_metadata,
)
from opc_browse.services.time_utils import (
    normalize_datetime_to_utc_naive_for_mysql,
    to_iso_utc,
)


def bucket_index_from_row(bucket_start_utc, bucket_seconds: int) -> int:
    normalized = to_iso_utc(bucket_start_utc)
    return int(normalized.timestamp() // bucket_seconds)


def run_relationship_analysis(conn, payload: RelationshipRequest) -> dict[str, Any]:
    actual_bucket_seconds = payload.resolved_bucket_seconds()
    start_utc = normalize_datetime_to_utc_naive_for_mysql(payload.start_utc)
    end_utc = normalize_datetime_to_utc_naive_for_mysql(payload.end_utc)

    target_metadata = fetch_target_tag_metadata(
        conn,
        machine_id=payload.target.machine_id,
        tag_id=payload.target.tag_id,
    )
    if not target_metadata:
        raise LookupError("Target tag not found")

    series_rows = fetch_bucketed_numeric_series(
        conn,
        machine_id=payload.target.machine_id,
        tag_ids=[payload.target.tag_id],
        start_utc=start_utc,
        end_utc=end_utc,
        bucket_seconds=actual_bucket_seconds,
    )

    target_series: dict[int, float] = {}
    for row in series_rows:
        bucket_index = bucket_index_from_row(row["bucket_start_utc"], actual_bucket_seconds)
        target_series[bucket_index] = float(row["avg_value"])
    if not target_series:
        raise LookupError("Target tag has no numeric samples in the requested window")

    if not is_target_series_usable(target_series, payload.min_pair_count):
        warnings: list[str] = []
        if actual_bucket_seconds > payload.bucket_seconds:
            warnings.append(
                "actual bucket_seconds was increased from "
                f"{payload.bucket_seconds} to {actual_bucket_seconds} "
                "to respect max_points_per_series"
            )
        warnings.append(
            "selected target did not have enough usable numeric data in this time range"
        )
        return {
            "target": {
                "machine_id": payload.target.machine_id,
                "tag_id": payload.target.tag_id,
                "label": payload.target.label
                or target_metadata.get("display_name")
                or target_metadata.get("browse_name")
                or target_metadata.get("opc_path"),
                "opc_path": target_metadata.get("opc_path"),
                "display_name": target_metadata.get("display_name"),
                "data_type": target_metadata.get("data_type"),
            },
            "window": {
                "start_utc": to_iso_utc(payload.start_utc),
                "end_utc": to_iso_utc(payload.end_utc),
                "requested_bucket_seconds": payload.bucket_seconds,
                "actual_bucket_seconds": actual_bucket_seconds,
            },
            "analysis": {
                "method": "stats_v1",
                "candidate_scope": payload.candidate_scope,
                "candidate_count_scanned": 0,
                "candidate_count_analyzed": 0,
                "skipped_count": 1,
                "skipped_by_reason": {SKIP_REASON_TARGET_INSUFFICIENT_DATA: 1},
                "max_lag_seconds": payload.max_lag_seconds,
                "min_pair_count": payload.min_pair_count,
                "warnings": warnings,
            },
            "results": [],
            "skipped": [{"tag_id": payload.target.tag_id, "reason": SKIP_REASON_TARGET_INSUFFICIENT_DATA}],
        }

    candidate_fetch = fetch_candidate_numeric_tags(
        conn,
        machine_id=payload.target.machine_id,
        target_tag_id=payload.target.tag_id,
        start_utc=start_utc,
        end_utc=end_utc,
        scope=payload.candidate_scope,
        candidate_tag_ids=payload.candidate_tag_ids,
        max_candidate_tags=payload.max_candidate_tags,
    )
    candidate_rows = candidate_fetch["rows"]

    tag_ids = [payload.target.tag_id, *[row["tag_id"] for row in candidate_rows]]
    if not tag_ids:
        raise ValueError("No tags available for analysis")

    series_rows = fetch_bucketed_numeric_series(
        conn,
        machine_id=payload.target.machine_id,
        tag_ids=tag_ids,
        start_utc=start_utc,
        end_utc=end_utc,
        bucket_seconds=actual_bucket_seconds,
    )

    series_by_tag_id: dict[int, dict[int, float]] = {tag_id: {} for tag_id in tag_ids}
    for row in series_rows:
        bucket_index = bucket_index_from_row(row["bucket_start_utc"], actual_bucket_seconds)
        series_by_tag_id.setdefault(row["tag_id"], {})[bucket_index] = float(row["avg_value"])

    target_series = series_by_tag_id.get(payload.target.tag_id, {})

    metadata_by_tag_id = {}
    for row in candidate_rows:
        metadata_by_tag_id[row["tag_id"]] = {
            "machine_id": row["machine_id"],
            "tag_id": row["tag_id"],
            "label": row.get("display_name") or row.get("browse_name") or row.get("opc_path"),
            "opc_path": row.get("opc_path"),
            "display_name": row.get("display_name"),
            "data_type": row.get("data_type"),
            "browse_name": row.get("browse_name"),
        }

    candidate_series_by_tag_id = {
        tag_id: series
        for tag_id, series in series_by_tag_id.items()
        if tag_id != payload.target.tag_id
    }
    analysis_result = analyze_relationships(
        target_series=target_series,
        candidate_series_by_tag_id=candidate_series_by_tag_id,
        metadata_by_tag_id=metadata_by_tag_id,
        bucket_seconds=actual_bucket_seconds,
        min_pair_count=payload.min_pair_count,
        max_lag_seconds=payload.max_lag_seconds,
        max_results=payload.max_results,
    )

    warnings: list[str] = []
    if actual_bucket_seconds > payload.bucket_seconds:
        warnings.append(
            "actual bucket_seconds was increased from "
            f"{payload.bucket_seconds} to {actual_bucket_seconds} "
            "to respect max_points_per_series"
        )
    if candidate_fetch["hit_limit"]:
        warnings.append(
            "candidate scan reached max_candidate_tags; results may be incomplete"
        )
    candidate_count_scanned = len(candidate_rows)
    candidate_count_analyzed = analysis_result["analyzed_count"]
    if candidate_count_scanned > 0 and candidate_count_analyzed <= max(2, candidate_count_scanned // 10):
        warnings.append("few candidates were analyzable after filtering")

    skipped_by_reason = summarize_skipped(analysis_result["skipped"])

    return {
        "target": {
            "machine_id": payload.target.machine_id,
            "tag_id": payload.target.tag_id,
            "label": payload.target.label
            or target_metadata.get("display_name")
            or target_metadata.get("browse_name")
            or target_metadata.get("opc_path"),
            "opc_path": target_metadata.get("opc_path"),
            "display_name": target_metadata.get("display_name"),
            "data_type": target_metadata.get("data_type"),
        },
        "window": {
            "start_utc": to_iso_utc(payload.start_utc),
            "end_utc": to_iso_utc(payload.end_utc),
            "requested_bucket_seconds": payload.bucket_seconds,
            "actual_bucket_seconds": actual_bucket_seconds,
        },
        "analysis": {
            "method": "stats_v1",
            "candidate_scope": payload.candidate_scope,
            "candidate_count_scanned": candidate_count_scanned,
            "candidate_count_analyzed": candidate_count_analyzed,
            "skipped_count": len(analysis_result["skipped"]),
            "skipped_by_reason": skipped_by_reason,
            "max_lag_seconds": payload.max_lag_seconds,
            "min_pair_count": payload.min_pair_count,
            "warnings": warnings,
        },
        "results": analysis_result["results"],
        "skipped": analysis_result["skipped"],
    }
