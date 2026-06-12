from datetime import datetime, timezone

from opc_browse.models import RelationshipRequest
from opc_browse.services import relationship_analysis as relationship_analysis_service
from opc_browse.services.correlation import SKIP_REASON_TARGET_INSUFFICIENT_DATA


def test_run_relationship_analysis_returns_early_for_weak_target(monkeypatch):
    payload = RelationshipRequest(
        target={"machine_id": 1, "tag_id": 123},
        start_utc=datetime(2026, 6, 11, 0, 0, tzinfo=timezone.utc),
        end_utc=datetime(2026, 6, 12, 0, 0, tzinfo=timezone.utc),
        bucket_seconds=60,
        max_points_per_series=2000,
        candidate_scope="same_machine",
        max_candidate_tags=300,
        max_results=25,
        min_pair_count=30,
        max_lag_seconds=1800,
    )

    monkeypatch.setattr(
        relationship_analysis_service,
        "fetch_target_tag_metadata",
        lambda *args, **kwargs: {
            "opc_path": "Area/Weak",
            "display_name": "Weak Target",
            "browse_name": "Weak Target",
            "data_type": "Double",
        },
    )
    monkeypatch.setattr(
        relationship_analysis_service,
        "fetch_bucketed_numeric_series",
        lambda *args, **kwargs: [
            {"tag_id": 123, "bucket_start_utc": datetime(2026, 6, 11, 0, 0), "avg_value": 1.0},
            {"tag_id": 123, "bucket_start_utc": datetime(2026, 6, 11, 0, 1), "avg_value": 1.0},
        ],
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("candidate fetch should not run for weak target")

    monkeypatch.setattr(
        relationship_analysis_service,
        "fetch_candidate_numeric_tags",
        fail_if_called,
    )

    response = relationship_analysis_service.run_relationship_analysis(object(), payload)
    assert response["analysis"]["candidate_count_scanned"] == 0
    assert response["analysis"]["candidate_count_analyzed"] == 0
    assert response["analysis"]["skipped_by_reason"] == {SKIP_REASON_TARGET_INSUFFICIENT_DATA: 1}
    assert response["results"] == []
