from __future__ import annotations

from datetime import datetime


ALLOWED_AGGREGATIONS = {
    "avg": "AVG(value_numeric)",
    "min": "MIN(value_numeric)",
    "max": "MAX(value_numeric)",
}


def build_tag_tree_filters(
    machine_id: int,
    search: str | None,
    numeric_only: bool,
    active_since_utc: datetime | None,
) -> tuple[str, list[object]]:
    del machine_id
    filters = ["WHERE 1 = 1"]
    params: list[object] = []

    if active_since_utc is not None:
        filters.append("AND ts.sampled_at_utc >= %s")
        params.append(active_since_utc)

    if search:
        filters.append(
            "AND ("
            "t.opc_path LIKE %s OR "
            "t.display_name LIKE %s OR "
            "t.browse_name LIKE %s OR "
            "t.parent_branch LIKE %s"
            ")"
        )
        search_value = f"%{search}%"
        params.extend([search_value, search_value, search_value, search_value])

    if numeric_only:
        filters.append(
            "AND ("
            "ts.value_numeric IS NOT NULL OR "
            "LOWER(COALESCE(t.data_type, '')) LIKE %s OR "
            "LOWER(COALESCE(t.data_type, '')) LIKE %s OR "
            "LOWER(COALESCE(t.data_type, '')) LIKE %s OR "
            "LOWER(COALESCE(t.data_type, '')) LIKE %s OR "
            "LOWER(COALESCE(t.data_type, '')) LIKE %s OR "
            "LOWER(COALESCE(t.data_type, '')) LIKE %s"
            ")"
        )
        params.extend(["%int%", "%float%", "%double%", "%decimal%", "%real%", "%number%"])

    return " ".join(filters), params


def build_bucket_expression(timestamp_column: str, bucket_seconds: int) -> str:
    if bucket_seconds < 1:
        raise ValueError("bucket_seconds must be >= 1")
    return (
        "FROM_UNIXTIME("
        f"FLOOR(UNIX_TIMESTAMP({timestamp_column}) / {bucket_seconds}) * {bucket_seconds}"
        ")"
    )


def build_in_clause(values: list[object]) -> tuple[str, list[object]]:
    if not values:
        raise ValueError("values must not be empty")
    placeholders = ",".join(["%s"] * len(values))
    return f"({placeholders})", list(values)


def get_aggregation_sql(aggregation: str) -> str:
    if aggregation not in ALLOWED_AGGREGATIONS:
        raise ValueError(f"Unsupported aggregation: {aggregation}")
    return ALLOWED_AGGREGATIONS[aggregation]
