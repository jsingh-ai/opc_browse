from opc_browse.services.diagnostics import (
    classify_tag_profile_flags,
    format_float,
    safe_percent,
    summarize_skipped,
)


def test_summarize_skipped_groups_by_reason():
    summary = summarize_skipped(
        [
            {"tag_id": 1, "reason": "insufficient_pair_count"},
            {"tag_id": 2, "reason": "insufficient_pair_count"},
            {"tag_id": 3, "reason": "constant_or_insufficient_variance"},
        ]
    )
    assert summary == {
        "insufficient_pair_count": 2,
        "constant_or_insufficient_variance": 1,
    }


def test_safe_percent_handles_zero_denominator():
    assert safe_percent(5, 0) is None
    assert safe_percent(1, 4) == 0.25


def test_format_float_handles_none_and_normal_values():
    assert format_float(None) == "-"
    assert format_float(1.23456) == "1.235"


def test_classify_tag_profile_flags_reuses_profile_rules():
    flags = classify_tag_profile_flags(
        {
            "sample_count": 100,
            "numeric_sample_count": 80,
            "null_numeric_count": 85,
            "error_count": 2,
            "distinct_numeric_count": 1,
        }
    )
    assert flags["has_numeric_data"] is True
    assert flags["mostly_null_numeric"] is True
    assert flags["appears_constant"] is True
    assert flags["has_errors"] is True
    assert flags["enough_samples"] is True
