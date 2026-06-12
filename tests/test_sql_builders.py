from datetime import datetime

import pytest

from opc_browse.services.sql_builders import (
    build_bucket_expression,
    build_in_clause,
    build_tag_tree_filters,
    get_aggregation_sql,
)


def test_build_tag_tree_filters_parameterizes_search_and_dates():
    where_sql, params = build_tag_tree_filters(
        machine_id=1,
        search="pump' OR 1=1 --",
        numeric_only=True,
        active_since_utc=datetime(2026, 6, 11, 0, 0, 0),
    )

    assert "pump' OR 1=1 --" not in where_sql
    assert "%s" in where_sql
    assert params[0] == datetime(2026, 6, 11, 0, 0, 0)
    assert "%pump' OR 1=1 --%" in params


def test_build_bucket_expression_uses_only_numeric_bucket_seconds():
    expression = build_bucket_expression("sampled_at_utc", 60)
    assert expression == (
        "FROM_UNIXTIME(FLOOR(UNIX_TIMESTAMP(sampled_at_utc) / 60) * 60)"
    )


def test_get_aggregation_sql_allows_known_values_only():
    assert get_aggregation_sql("avg") == "AVG(value_numeric)"
    with pytest.raises(ValueError):
        get_aggregation_sql("avg); DROP TABLE tag_samples; --")


def test_build_in_clause_returns_placeholders_without_interpolating_values():
    clause, params = build_in_clause([1, "tag' OR 1=1 --", 3])
    assert clause == "(%s,%s,%s)"
    assert "tag' OR 1=1 --" not in clause
    assert params == [1, "tag' OR 1=1 --", 3]


def test_build_in_clause_rejects_empty_values():
    with pytest.raises(ValueError):
        build_in_clause([])
