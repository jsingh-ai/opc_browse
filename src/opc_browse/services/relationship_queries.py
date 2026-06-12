from __future__ import annotations

from datetime import datetime

from opc_browse.services.sql_builders import build_bucket_expression, build_in_clause


def fetch_target_tag_metadata(conn, machine_id: int, tag_id: int) -> dict | None:
    sql = """
        SELECT
            %s AS machine_id,
            t.id AS tag_id,
            t.opc_path,
            t.display_name,
            t.browse_name,
            t.data_type,
            t.parent_branch
        FROM tags t
        WHERE t.id = %s
          AND EXISTS (
              SELECT 1
              FROM tag_samples ts
              WHERE ts.machine_id = %s
                AND ts.tag_id = t.id
          )
        LIMIT 1
    """
    with conn.cursor() as cursor:
        cursor.execute(sql, (machine_id, tag_id, machine_id))
        return cursor.fetchone()


def fetch_candidate_numeric_tags(
    conn,
    machine_id: int,
    target_tag_id: int,
    start_utc: datetime,
    end_utc: datetime,
    scope: str,
    candidate_tag_ids: list[int] | None,
    max_candidate_tags: int,
) -> dict:
    filters = [
        "ts.machine_id = %s",
        "ts.sampled_at_utc >= %s",
        "ts.sampled_at_utc < %s",
        "ts.value_numeric IS NOT NULL",
        "t.id <> %s",
    ]
    params: list[object] = [machine_id, start_utc, end_utc, target_tag_id]

    if scope == "same_folder":
        target_row = fetch_target_tag_metadata(conn, machine_id, target_tag_id)
        if not target_row:
            return {"rows": [], "hit_limit": False}
        target_path = target_row.get("opc_path") or ""
        if "/" in target_path:
            parent_prefix = target_path.rsplit("/", 1)[0]
            filters.append("t.opc_path LIKE %s")
            params.append(f"{parent_prefix}/%")
        else:
            filters.append("t.opc_path NOT LIKE %s")
            params.append("%/%")
    elif scope == "selected_tags":
        selected_tag_ids = [tag_id for tag_id in (candidate_tag_ids or []) if tag_id != target_tag_id]
        if not selected_tag_ids:
            return {"rows": [], "hit_limit": False}
        in_clause, in_params = build_in_clause(selected_tag_ids)
        filters.append(f"t.id IN {in_clause}")
        params.extend(in_params)

    sql = f"""
        SELECT
            %s AS machine_id,
            t.id AS tag_id,
            t.opc_path,
            t.display_name,
            t.browse_name,
            t.data_type,
            t.parent_branch,
            COUNT(*) AS numeric_sample_count
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
        ORDER BY numeric_sample_count DESC, t.opc_path ASC
        LIMIT %s
    """
    query_params = [machine_id, *params, max_candidate_tags + 1]
    with conn.cursor() as cursor:
        cursor.execute(sql, query_params)
        rows = cursor.fetchall()
    hit_limit = len(rows) > max_candidate_tags
    return {"rows": rows[:max_candidate_tags], "hit_limit": hit_limit}


def fetch_bucketed_numeric_series(
    conn,
    machine_id: int,
    tag_ids: list[int],
    start_utc: datetime,
    end_utc: datetime,
    bucket_seconds: int,
) -> list[dict]:
    in_clause, in_params = build_in_clause(tag_ids)
    bucket_expr = build_bucket_expression("sampled_at_utc", bucket_seconds)
    sql = f"""
        SELECT
            tag_id,
            {bucket_expr} AS bucket_start_utc,
            AVG(value_numeric) AS avg_value,
            COUNT(*) AS sample_count
        FROM tag_samples
        WHERE machine_id = %s
          AND tag_id IN {in_clause}
          AND sampled_at_utc >= %s
          AND sampled_at_utc < %s
          AND value_numeric IS NOT NULL
        GROUP BY tag_id, bucket_start_utc
        ORDER BY tag_id ASC, bucket_start_utc ASC
    """
    params = [machine_id, *in_params, start_utc, end_utc]
    with conn.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()
