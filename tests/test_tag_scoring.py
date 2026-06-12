from datetime import datetime, timedelta, timezone

from opc_browse.services.tag_scoring import (
    classify_constant,
    classify_counter_like,
    classify_sparse,
    classify_stale,
    classify_state_like_numeric,
    coefficient_of_variation,
    infer_semantic_type,
    score_tag_usefulness,
)


def test_coefficient_of_variation_handles_normal_and_zero_average():
    assert coefficient_of_variation(10.0, 2.0) == 0.2
    assert coefficient_of_variation(0.0, 2.0) is None


def test_classify_constant_true_for_single_distinct_value():
    assert classify_constant(
        {
            "numeric_sample_count": 10,
            "distinct_numeric_count": 1,
            "min_value": 5.0,
            "max_value": 5.0,
        }
    )


def test_classify_sparse_true_for_mostly_null_numeric():
    assert classify_sparse(
        {
            "sample_count": 100,
            "numeric_sample_count": 10,
            "null_numeric_count": 85,
        }
    )


def test_classify_counter_like_for_increasing_numeric_series():
    assert classify_counter_like(
        {
            "numeric_sample_count": 100,
            "distinct_numeric_count": 50,
            "min_value": 0.0,
            "max_value": 1000.0,
            "stddev_value": 50.0,
        }
    )


def test_classify_state_like_numeric_for_small_discrete_range():
    assert classify_state_like_numeric(
        {
            "numeric_sample_count": 100,
            "distinct_numeric_count": 4,
            "min_value": 0.0,
            "max_value": 3.0,
            "data_type": "Int32",
        }
    )


def test_classify_stale_uses_utc_window():
    now = datetime(2026, 6, 12, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(hours=25)
    recent = now - timedelta(hours=2)
    assert classify_stale(old, now) is True
    assert classify_stale(recent, now) is False


def test_score_tag_usefulness_high_for_recent_changing_numeric_tag():
    now = datetime(2026, 6, 12, 12, 0, tzinfo=timezone.utc)
    score = score_tag_usefulness(
        {
            "sample_count": 500,
            "numeric_sample_count": 500,
            "text_sample_count": 0,
            "null_numeric_count": 0,
            "error_count": 0,
            "last_seen_utc": now,
            "min_value": 10.0,
            "max_value": 80.0,
            "avg_value": 45.0,
            "stddev_value": 8.0,
            "distinct_numeric_count": 120,
            "quality_good_count": 490,
            "quality_bad_count": 10,
            "now_utc": now,
        }
    )
    assert score["score"] >= 75
    assert score["grade"] == "high"
    assert score["semantic_type"] in {"continuous_numeric", "counter_like"}


def test_score_tag_usefulness_ignore_for_stale_constant_sparse_tag():
    now = datetime(2026, 6, 12, 12, 0, tzinfo=timezone.utc)
    score = score_tag_usefulness(
        {
            "sample_count": 20,
            "numeric_sample_count": 3,
            "text_sample_count": 0,
            "null_numeric_count": 18,
            "error_count": 5,
            "last_seen_utc": now - timedelta(days=4),
            "min_value": 1.0,
            "max_value": 1.0,
            "avg_value": 1.0,
            "stddev_value": 0.0,
            "distinct_numeric_count": 1,
            "quality_good_count": 0,
            "quality_bad_count": 20,
            "now_utc": now,
        }
    )
    assert score["score"] <= 25
    assert score["grade"] == "ignore"
    assert "constant" in score["badges"]


def test_infer_semantic_type_covers_expected_cases():
    assert infer_semantic_type({"text_sample_count": 5, "numeric_sample_count": 0}) == "text_or_state"
    assert infer_semantic_type(
        {"sample_count": 100, "numeric_sample_count": 10, "null_numeric_count": 90}
    ) == "sparse"
    assert infer_semantic_type(
        {"numeric_sample_count": 10, "distinct_numeric_count": 1, "min_value": 3.0, "max_value": 3.0}
    ) == "constant"
