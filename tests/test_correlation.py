from opc_browse.services.correlation import (
    SKIP_REASON_CANDIDATE_INSUFFICIENT_OVERLAP,
    SKIP_REASON_CONSTANT_OR_INSUFFICIENT_VARIANCE,
    SKIP_REASON_NON_NUMERIC_OR_MISSING_SERIES,
    SKIP_REASON_TARGET_INSUFFICIENT_DATA,
    analyze_relationships,
    best_lagged_corr,
    classify_relationship,
    first_difference,
    is_target_series_usable,
    pearson_corr,
)


def test_pearson_corr_identical_series_is_positive_one():
    corr = pearson_corr([1, 2, 3, 4], [1, 2, 3, 4], min_pair_count=3)
    assert corr is not None
    assert corr > 0.999


def test_pearson_corr_inverse_series_is_negative_one():
    corr = pearson_corr([1, 2, 3, 4], [4, 3, 2, 1], min_pair_count=3)
    assert corr is not None
    assert corr < -0.999


def test_pearson_corr_ignores_missing_values():
    corr = pearson_corr([1, None, 3, 4], [1, 2, 3, 4], min_pair_count=3)
    assert corr is not None
    assert corr > 0.999


def test_pearson_corr_returns_none_for_constant_series():
    assert pearson_corr([1, 1, 1, 1], [1, 2, 3, 4], min_pair_count=3) is None


def test_first_difference_preserves_missing_values_as_none():
    assert first_difference([1, 3, None, 10, 13]) == [2.0, None, None, 3.0]


def test_best_lagged_corr_detects_candidate_leading_target():
    candidate = [1, 4, 1, 5, 2, 6, 3, 7, 4]
    target = [None, None, 1, 4, 1, 5, 2, 6, 3]
    corr, lag_buckets, pair_count = best_lagged_corr(
        target,
        candidate,
        max_lag_buckets=3,
        min_pair_count=4,
    )
    assert corr is not None
    assert corr > 0.99
    assert lag_buckets == 2
    assert pair_count >= 4


def test_classify_relationship_marks_possible_effect_for_negative_lag():
    result = classify_relationship(
        same_time_corr=0.4,
        delta_corr=0.3,
        best_lag_corr=0.9,
        best_lag_buckets=-2,
        bucket_seconds=60,
    )
    assert result["relationship_type"] == "possible_effect"
    assert result["best_lag_seconds"] == -120


def test_delta_corr_can_exceed_same_time_corr():
    target = [0, 1, 0, 2, 1, 3, 2]
    candidate = [100, 115, 110, 135, 130, 155, 150]
    same_time_corr = pearson_corr(target, candidate, min_pair_count=5)
    delta_corr = pearson_corr(
        first_difference(target),
        first_difference(candidate),
        min_pair_count=5,
    )
    assert same_time_corr is not None
    assert delta_corr is not None
    assert delta_corr > same_time_corr


def test_analyze_relationships_ranks_stronger_relationships_first():
    target_series = {0: 0.0, 1: 1.0, 2: 2.0, 3: 3.0, 4: 4.0, 5: 5.0}
    candidate_series_by_tag_id = {
        10: {0: 0.0, 1: 1.0, 2: 2.0, 3: 3.0, 4: 4.0, 5: 5.0},
        20: {0: 0.0, 1: 0.8, 2: 2.2, 3: 2.8, 4: 4.2, 5: 5.1},
        30: {0: 2.0, 1: 2.0, 2: 2.0, 3: 2.0, 4: 2.0, 5: 2.0},
    }
    metadata_by_tag_id = {
        10: {"machine_id": 1, "display_name": "Strong", "opc_path": "A/Strong", "data_type": "Double"},
        20: {"machine_id": 1, "display_name": "Weak", "opc_path": "A/Weak", "data_type": "Double"},
        30: {"machine_id": 1, "display_name": "Constant", "opc_path": "A/Constant", "data_type": "Double"},
    }

    result = analyze_relationships(
        target_series=target_series,
        candidate_series_by_tag_id=candidate_series_by_tag_id,
        metadata_by_tag_id=metadata_by_tag_id,
        bucket_seconds=60,
        min_pair_count=4,
        max_lag_seconds=120,
        max_results=5,
    )

    assert [item["tag_id"] for item in result["results"]][:2] == [10, 20]
    assert result["analyzed_count"] == 2
    assert result["skipped"][0]["tag_id"] == 30
    assert result["skipped"][0]["reason"] == SKIP_REASON_CONSTANT_OR_INSUFFICIENT_VARIANCE


def test_analyze_relationships_enforces_max_results():
    target_series = {0: 0.0, 1: 1.0, 2: 2.0, 3: 3.0, 4: 4.0}
    candidate_series_by_tag_id = {
        10: {0: 0.0, 1: 1.0, 2: 2.0, 3: 3.0, 4: 4.0},
        20: {0: 0.0, 1: 1.0, 2: 2.0, 3: 3.0, 4: 4.1},
    }
    metadata_by_tag_id = {
        10: {"machine_id": 1, "display_name": "Top", "opc_path": "A/Top", "data_type": "Double"},
        20: {"machine_id": 1, "display_name": "Second", "opc_path": "A/Second", "data_type": "Double"},
    }

    result = analyze_relationships(
        target_series=target_series,
        candidate_series_by_tag_id=candidate_series_by_tag_id,
        metadata_by_tag_id=metadata_by_tag_id,
        bucket_seconds=60,
        min_pair_count=3,
        max_lag_seconds=60,
        max_results=1,
    )

    assert len(result["results"]) == 1


def test_analyze_relationships_marks_missing_candidate_series_consistently():
    result = analyze_relationships(
        target_series={0: 1.0, 1: 2.0, 2: 3.0, 3: 4.0},
        candidate_series_by_tag_id={10: {}},
        metadata_by_tag_id={10: {"machine_id": 1, "opc_path": "A/Missing"}},
        bucket_seconds=60,
        min_pair_count=3,
        max_lag_seconds=60,
        max_results=10,
    )
    assert result["results"] == []
    assert result["skipped"][0]["reason"] == SKIP_REASON_NON_NUMERIC_OR_MISSING_SERIES


def test_analyze_relationships_marks_target_insufficient_data_consistently():
    result = analyze_relationships(
        target_series={0: 1.0, 1: 1.0},
        candidate_series_by_tag_id={10: {0: 1.0, 1: 2.0, 2: 3.0}},
        metadata_by_tag_id={10: {"machine_id": 1, "opc_path": "A/Candidate"}},
        bucket_seconds=60,
        min_pair_count=3,
        max_lag_seconds=60,
        max_results=10,
    )
    assert result["results"] == []
    assert result["skipped"][0]["reason"] == SKIP_REASON_TARGET_INSUFFICIENT_DATA


def test_analyze_relationships_marks_insufficient_overlap_consistently():
    result = analyze_relationships(
        target_series={0: 1.0, 1: 2.0, 2: 3.0, 3: 4.0},
        candidate_series_by_tag_id={10: {10: 5.0, 11: 6.0}},
        metadata_by_tag_id={10: {"machine_id": 1, "opc_path": "A/FarAway"}},
        bucket_seconds=60,
        min_pair_count=3,
        max_lag_seconds=60,
        max_results=10,
    )
    assert result["results"] == []
    assert result["skipped"][0]["reason"] == SKIP_REASON_CANDIDATE_INSUFFICIENT_OVERLAP


def test_is_target_series_usable_rejects_short_or_constant_target():
    assert is_target_series_usable({0: 1.0, 1: 2.0}, min_pair_count=3) is False
    assert is_target_series_usable({0: 1.0, 1: 1.0, 2: 1.0}, min_pair_count=3) is False
    assert is_target_series_usable({0: 1.0, 1: 2.0, 2: 3.0}, min_pair_count=3) is True
