from datetime import datetime, timezone

from opc_browse.models import RelationshipResponse
from opc_browse.services.snapshots import (
    compare_snapshots,
    default_snapshot_path,
    relationship_response_to_jsonable,
)


def test_default_snapshot_path_contains_machine_tag_and_json_suffix():
    path = default_snapshot_path(1, 123)
    assert "1" in str(path)
    assert "123" in str(path)
    assert str(path).endswith(".json")


def test_compare_snapshots_detects_added_removed_and_common_tags():
    snapshot_a = {"results": [{"tag_id": 1}, {"tag_id": 2}]}
    snapshot_b = {"results": [{"tag_id": 2}, {"tag_id": 3}]}
    comparison = compare_snapshots(snapshot_a, snapshot_b)
    assert comparison["added_tag_ids"] == [3]
    assert comparison["removed_tag_ids"] == [1]
    assert comparison["common_tag_ids"] == [2]


def test_compare_snapshots_detects_score_changes():
    snapshot_a = {"results": [{"tag_id": 1, "score": 0.5}]}
    snapshot_b = {"results": [{"tag_id": 1, "score": 0.9}]}
    comparison = compare_snapshots(snapshot_a, snapshot_b)
    assert comparison["score_changes"][0]["score_delta"] == 0.4


def test_compare_snapshots_detects_relationship_type_changes():
    snapshot_a = {"results": [{"tag_id": 1, "relationship_type": "moves_together"}]}
    snapshot_b = {"results": [{"tag_id": 1, "relationship_type": "possible_driver"}]}
    comparison = compare_snapshots(snapshot_a, snapshot_b)
    assert comparison["relationship_type_changes"][0]["relationship_type_a"] == "moves_together"
    assert comparison["relationship_type_changes"][0]["relationship_type_b"] == "possible_driver"


def test_relationship_response_to_jsonable_handles_model_and_datetimes():
    payload = RelationshipResponse(
        target={
            "machine_id": 1,
            "tag_id": 123,
            "label": "Target",
            "opc_path": "Area/Target",
            "display_name": "Target",
            "data_type": "Double",
        },
        window={
            "start_utc": datetime(2026, 6, 11, 0, 0, 0, tzinfo=timezone.utc),
            "end_utc": datetime(2026, 6, 12, 0, 0, 0, tzinfo=timezone.utc),
            "requested_bucket_seconds": 60,
            "actual_bucket_seconds": 60,
        },
        analysis={
            "method": "stats_v1",
            "candidate_scope": "same_machine",
            "candidate_count_scanned": 10,
            "candidate_count_analyzed": 4,
            "skipped_count": 1,
            "skipped_by_reason": {"insufficient_pair_count": 1},
            "max_lag_seconds": 1800,
            "min_pair_count": 30,
            "warnings": [],
        },
        results=[],
        skipped=[],
    )
    jsonable = relationship_response_to_jsonable(payload)
    assert jsonable["window"]["start_utc"] == "2026-06-11T00:00:00+00:00"
