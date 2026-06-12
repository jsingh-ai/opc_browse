from __future__ import annotations

from fastapi import APIRouter

from opc_browse.db import connection_context
from opc_browse.models import (
    TimeseriesPoint,
    TimeseriesQueryRequest,
    TimeseriesQueryResponse,
    TimeseriesSeriesOut,
)
from opc_browse.services.sql_builders import build_bucket_expression, get_aggregation_sql
from opc_browse.services.time_utils import (
    normalize_datetime_to_utc_naive_for_mysql,
    to_iso_utc,
)


router = APIRouter(tags=["timeseries"])


@router.post("/timeseries/query", response_model=TimeseriesQueryResponse)
def query_timeseries(payload: TimeseriesQueryRequest):
    resolved_bucket_seconds = payload.resolved_bucket_seconds()
    bucket_expr = build_bucket_expression("sampled_at_utc", resolved_bucket_seconds)
    aggregation_sql = get_aggregation_sql(payload.aggregation)

    series_results: list[TimeseriesSeriesOut] = []
    with connection_context() as connection:
        with connection.cursor() as cursor:
            for requested_series in payload.series:
                sql = f"""
                    SELECT
                        {bucket_expr} AS bucket_start_utc,
                        {aggregation_sql} AS aggregated_value,
                        COUNT(*) AS sample_count,
                        MIN(value_numeric) AS min_value,
                        MAX(value_numeric) AS max_value
                    FROM tag_samples
                    WHERE machine_id = %s
                      AND tag_id = %s
                      AND sampled_at_utc >= %s
                      AND sampled_at_utc < %s
                      AND value_numeric IS NOT NULL
                    GROUP BY bucket_start_utc
                    ORDER BY bucket_start_utc ASC
                """
                params = (
                    requested_series.machine_id,
                    requested_series.tag_id,
                    normalize_datetime_to_utc_naive_for_mysql(payload.start_utc),
                    normalize_datetime_to_utc_naive_for_mysql(payload.end_utc),
                )
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                points = [
                    TimeseriesPoint(
                        t=to_iso_utc(row["bucket_start_utc"]),
                        v=float(row["aggregated_value"]),
                        sample_count=int(row["sample_count"]),
                        min_value=float(row["min_value"]),
                        max_value=float(row["max_value"]),
                    )
                    for row in rows
                ]
                series_results.append(
                    TimeseriesSeriesOut(
                        machine_id=requested_series.machine_id,
                        tag_id=requested_series.tag_id,
                        label=requested_series.label,
                        points=points,
                    )
                )

    return TimeseriesQueryResponse(
        bucket_seconds=resolved_bucket_seconds,
        aggregation=payload.aggregation,
        series=series_results,
    )
