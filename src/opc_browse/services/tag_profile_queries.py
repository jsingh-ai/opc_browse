from __future__ import annotations

from datetime import datetime

from opc_browse.services.tag_scoring import score_tag_usefulness


def _coerce_profile_row(row: dict) -> dict:
    normalized = {
        "machine_id": int(row.get("machine_id") or 0),
        "tag_id": int(row.get("tag_id") or 0),
        "opc_path": row.get("opc_path"),
        "display_name": row.get("display_name"),
        "browse_name": row.get("browse_name"),
        "data_type": row.get("data_type"),
        "parent_branch": row.get("parent_branch"),
        "sample_count": int(row.get("sample_count") or 0),
        "numeric_sample_count": int(row.get("numeric_sample_count") or 0),
        "text_sample_count": int(row.get("text_sample_count") or 0),
        "null_numeric_count": int(row.get("null_numeric_count") or 0),
        "error_count": int(row.get("error_count") or 0),
        "first_seen_utc": row.get("first_seen_utc"),
        "last_seen_utc": row.get("last_seen_utc"),
        "min_value": row.get("min_value"),
        "max_value": row.get("max_value"),
        "avg_value": row.get("avg_value"),
        "stddev_value": row.get("stddev_value"),
        "distinct_numeric_count": int(row.get("distinct_numeric_count") or 0),
        "quality_good_count": int(row.get("quality_good_count") or 0),
        "quality_bad_count": int(row.get("quality_bad_count") or 0),
    }
    normalized["usefulness_score"] = score_tag_usefulness(normalized)
    return normalized


def _order_key(profile: dict, order_by: str):
    if order_by == "last_seen":
        return (profile.get("last_seen_utc") is None, profile.get("last_seen_utc"))
    if order_by == "sample_count":
        return profile.get("sample_count") or 0
    if order_by == "display_name":
        return (
            profile.get("display_name")
            or profile.get("browse_name")
            or profile.get("opc_path")
            or ""
        ).lower()
    return profile.get("usefulness_score", {}).get("score", 0)


def _sort_profiles(profiles: list[dict], order_by: str) -> list[dict]:
    if order_by == "display_name":
        return sorted(profiles, key=lambda item: _order_key(item, order_by))
    return sorted(profiles, key=lambda item: _order_key(item, order_by), reverse=True)


def fetch_machine_tag_profiles(
    conn,
    machine_id: int,
    start_utc: datetime | None = None,
    end_utc: datetime | None = None,
    search: str | None = None,
    numeric_only: bool = False,
    limit: int = 1000,
    order_by: str = "score",
) -> list[dict]:
    filters = ["ts.machine_id = %s"]
    params: list[object] = [machine_id]

    if start_utc is not None:
        filters.append("ts.sampled_at_utc >= %s")
        params.append(start_utc)
    if end_utc is not None:
        filters.append("ts.sampled_at_utc < %s")
        params.append(end_utc)
    if search:
        search_value = f"%{search}%"
        filters.append(
            "("
            "t.opc_path LIKE %s OR "
            "t.display_name LIKE %s OR "
            "t.browse_name LIKE %s OR "
            "t.parent_branch LIKE %s"
            ")"
        )
        params.extend([search_value, search_value, search_value, search_value])
    if numeric_only:
        filters.append(
            "("
            "ts.value_numeric IS NOT NULL OR "
            "LOWER(COALESCE(t.data_type, '')) LIKE %s OR "
            "LOWER(COALESCE(t.data_type, '')) LIKE %s OR "
            "LOWER(COALESCE(t.data_type, '')) LIKE %s OR "
            "LOWER(COALESCE(t.data_type, '')) LIKE %s"
            ")"
        )
        params.extend(["%int%", "%float%", "%double%", "%decimal%"])

    sql = f"""
        SELECT
            %s AS machine_id,
            t.id AS tag_id,
            t.opc_path,
            t.display_name,
            t.browse_name,
            t.data_type,
            t.parent_branch,
            COUNT(ts.id) AS sample_count,
            SUM(CASE WHEN ts.value_numeric IS NOT NULL THEN 1 ELSE 0 END) AS numeric_sample_count,
            SUM(CASE WHEN ts.value_text IS NOT NULL AND ts.value_text <> '' THEN 1 ELSE 0 END) AS text_sample_count,
            SUM(CASE WHEN ts.value_numeric IS NULL THEN 1 ELSE 0 END) AS null_numeric_count,
            SUM(CASE WHEN ts.error_text IS NOT NULL AND ts.error_text <> '' THEN 1 ELSE 0 END) AS error_count,
            MIN(ts.sampled_at_utc) AS first_seen_utc,
            MAX(ts.sampled_at_utc) AS last_seen_utc,
            MIN(ts.value_numeric) AS min_value,
            MAX(ts.value_numeric) AS max_value,
            AVG(ts.value_numeric) AS avg_value,
            STDDEV_SAMP(ts.value_numeric) AS stddev_value,
            COUNT(DISTINCT ts.value_numeric) AS distinct_numeric_count,
            SUM(CASE WHEN LOWER(COALESCE(ts.quality, '')) LIKE %s THEN 1 ELSE 0 END) AS quality_good_count,
            SUM(
                CASE
                    WHEN ts.error_text IS NOT NULL AND ts.error_text <> '' THEN 1
                    WHEN ts.quality IS NOT NULL AND LOWER(COALESCE(ts.quality, '')) NOT LIKE %s THEN 1
                    ELSE 0
                END
            ) AS quality_bad_count
        FROM tags t
        INNER JOIN tag_samples ts
            ON ts.tag_id = t.id
        WHERE {" AND ".join(filters)}
        GROUP BY
            t.id,
            t.opc_path,
            t.display_name,
            t.browse_name,
            t.data_type,
            t.parent_branch
        ORDER BY sample_count DESC, t.opc_path ASC
        LIMIT %s
    """
    query_params = [machine_id, "%good%", "%good%", *params, limit]
    with conn.cursor() as cursor:
        cursor.execute(sql, query_params)
        rows = cursor.fetchall()

    profiles = [_coerce_profile_row(row) for row in rows]
    return _sort_profiles(profiles, order_by)


def fetch_tag_profile_stats(
    conn,
    machine_id: int,
    tag_id: int,
    start_utc: datetime | None = None,
    end_utc: datetime | None = None,
) -> dict | None:
    filters = ["ts.machine_id = %s", "t.id = %s"]
    params: list[object] = [machine_id, tag_id]

    if start_utc is not None:
        filters.append("ts.sampled_at_utc >= %s")
        params.append(start_utc)
    if end_utc is not None:
        filters.append("ts.sampled_at_utc < %s")
        params.append(end_utc)

    sql = f"""
        SELECT
            %s AS machine_id,
            t.id AS tag_id,
            t.opc_path,
            t.display_name,
            t.browse_name,
            t.data_type,
            t.parent_branch,
            COUNT(ts.id) AS sample_count,
            SUM(CASE WHEN ts.value_numeric IS NOT NULL THEN 1 ELSE 0 END) AS numeric_sample_count,
            SUM(CASE WHEN ts.value_text IS NOT NULL AND ts.value_text <> '' THEN 1 ELSE 0 END) AS text_sample_count,
            SUM(CASE WHEN ts.value_numeric IS NULL THEN 1 ELSE 0 END) AS null_numeric_count,
            SUM(CASE WHEN ts.error_text IS NOT NULL AND ts.error_text <> '' THEN 1 ELSE 0 END) AS error_count,
            MIN(ts.sampled_at_utc) AS first_seen_utc,
            MAX(ts.sampled_at_utc) AS last_seen_utc,
            MIN(ts.value_numeric) AS min_value,
            MAX(ts.value_numeric) AS max_value,
            AVG(ts.value_numeric) AS avg_value,
            STDDEV_SAMP(ts.value_numeric) AS stddev_value,
            COUNT(DISTINCT ts.value_numeric) AS distinct_numeric_count,
            SUM(CASE WHEN LOWER(COALESCE(ts.quality, '')) LIKE %s THEN 1 ELSE 0 END) AS quality_good_count,
            SUM(
                CASE
                    WHEN ts.error_text IS NOT NULL AND ts.error_text <> '' THEN 1
                    WHEN ts.quality IS NOT NULL AND LOWER(COALESCE(ts.quality, '')) NOT LIKE %s THEN 1
                    ELSE 0
                END
            ) AS quality_bad_count
        FROM tags t
        INNER JOIN tag_samples ts
            ON ts.tag_id = t.id
        WHERE {" AND ".join(filters)}
        GROUP BY
            t.id,
            t.opc_path,
            t.display_name,
            t.browse_name,
            t.data_type,
            t.parent_branch
        LIMIT 1
    """
    query_params = [machine_id, "%good%", "%good%", *params]
    with conn.cursor() as cursor:
        cursor.execute(sql, query_params)
        row = cursor.fetchone()
    if not row:
        return None
    return _coerce_profile_row(row)
