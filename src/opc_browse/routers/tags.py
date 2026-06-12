from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from opc_browse.db import connection_context
from opc_browse.models import TagProfileOut, TagTreeNode, UsefulnessFlags
from opc_browse.services.diagnostics import classify_tag_profile_flags
from opc_browse.services.sql_builders import build_tag_tree_filters
from opc_browse.services.tag_tree import build_tag_tree
from opc_browse.services.time_utils import normalize_datetime_to_utc_naive_for_mysql


router = APIRouter(tags=["tags"])


NUMERIC_TYPES = {
    "float",
    "double",
    "decimal",
    "int",
    "integer",
    "short",
    "long",
    "byte",
    "sbyte",
    "uint",
    "ulong",
    "ushort",
    "number",
    "real",
}


def _is_numeric_type(data_type: str | None) -> bool:
    if not data_type:
        return False
    normalized = data_type.strip().lower()
    return any(token in normalized for token in NUMERIC_TYPES)


@router.get(
    "/machines/{machine_id}/tags/tree",
    response_model=TagTreeNode,
)
def get_machine_tag_tree(
    machine_id: int,
    search: str | None = None,
    numeric_only: bool = False,
    active_since_utc: datetime | None = Query(default=None),
):
    where_sql, params = build_tag_tree_filters(
        machine_id=machine_id,
        search=search,
        numeric_only=numeric_only,
        active_since_utc=normalize_datetime_to_utc_naive_for_mysql(active_since_utc),
    )
    sql = f"""
        SELECT
            t.id AS tag_id,
            t.opc_path,
            t.display_name,
            t.browse_name,
            t.data_type,
            t.parent_branch,
            MAX(ts.sampled_at_utc) AS last_seen_utc,
            COUNT(ts.id) AS sample_count,
            MAX(CASE WHEN ts.value_numeric IS NOT NULL THEN 1 ELSE 0 END) AS has_numeric_samples
        FROM tags t
        INNER JOIN tag_samples ts
            ON ts.tag_id = t.id
            AND ts.machine_id = %s
        {where_sql}
        GROUP BY
            t.id,
            t.opc_path,
            t.display_name,
            t.browse_name,
            t.data_type,
            t.parent_branch
        ORDER BY t.opc_path ASC, t.display_name ASC, t.browse_name ASC
    """
    query_params = [machine_id, *params]
    with connection_context() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, query_params)
            rows = cursor.fetchall()

    for row in rows:
        row["sample_count"] = int(row["sample_count"] or 0)
        row["is_numeric"] = bool(row.pop("has_numeric_samples")) or _is_numeric_type(
            row.get("data_type")
        )

    return build_tag_tree(rows)


@router.get(
    "/machines/{machine_id}/tags/{tag_id}/profile",
    response_model=TagProfileOut,
)
def get_tag_profile(
    machine_id: int,
    tag_id: int,
    start_utc: datetime | None = Query(default=None),
    end_utc: datetime | None = Query(default=None),
):
    filters = ["machine_id = %s", "tag_id = %s"]
    params: list[object] = [machine_id, tag_id]

    if start_utc is not None:
        filters.append("sampled_at_utc >= %s")
        params.append(normalize_datetime_to_utc_naive_for_mysql(start_utc))
    if end_utc is not None:
        filters.append("sampled_at_utc < %s")
        params.append(normalize_datetime_to_utc_naive_for_mysql(end_utc))

    where_sql = " AND ".join(filters)
    summary_sql = f"""
        SELECT
            machine_id,
            tag_id,
            COUNT(*) AS sample_count,
            SUM(CASE WHEN value_numeric IS NOT NULL THEN 1 ELSE 0 END) AS numeric_sample_count,
            SUM(CASE WHEN value_text IS NOT NULL AND value_text <> '' THEN 1 ELSE 0 END) AS text_sample_count,
            SUM(CASE WHEN value_numeric IS NULL THEN 1 ELSE 0 END) AS null_numeric_count,
            SUM(CASE WHEN error_text IS NOT NULL AND error_text <> '' THEN 1 ELSE 0 END) AS error_count,
            MIN(sampled_at_utc) AS first_seen_utc,
            MAX(sampled_at_utc) AS last_seen_utc,
            MIN(value_numeric) AS min_value,
            MAX(value_numeric) AS max_value,
            AVG(value_numeric) AS avg_value,
            STDDEV_SAMP(value_numeric) AS stddev_value,
            COUNT(DISTINCT value_numeric) AS distinct_numeric_count
        FROM tag_samples
        WHERE {where_sql}
        GROUP BY machine_id, tag_id
    """
    quality_sql = f"""
        SELECT
            quality,
            status_code,
            COUNT(*) AS count
        FROM tag_samples
        WHERE {where_sql}
        GROUP BY quality, status_code
        ORDER BY count DESC, quality ASC, status_code ASC
    """

    with connection_context() as connection:
        with connection.cursor() as cursor:
            cursor.execute(summary_sql, params)
            summary = cursor.fetchone()
            if not summary:
                raise HTTPException(status_code=404, detail="Tag profile not found")

            cursor.execute(quality_sql, params)
            quality_rows = cursor.fetchall()

    sample_count = int(summary["sample_count"] or 0)
    numeric_sample_count = int(summary["numeric_sample_count"] or 0)
    null_numeric_count = int(summary["null_numeric_count"] or 0)
    error_count = int(summary["error_count"] or 0)
    distinct_numeric_count = int(summary["distinct_numeric_count"] or 0)

    flags = UsefulnessFlags(
        **classify_tag_profile_flags(
            {
                "sample_count": sample_count,
                "numeric_sample_count": numeric_sample_count,
                "null_numeric_count": null_numeric_count,
                "error_count": error_count,
                "distinct_numeric_count": distinct_numeric_count,
            }
        )
    )

    summary["quality_breakdown"] = quality_rows
    summary["usefulness_flags"] = flags
    return summary
