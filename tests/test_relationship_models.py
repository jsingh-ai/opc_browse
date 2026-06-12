from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from opc_browse.models import RelationshipRequest


def test_relationship_request_accepts_valid_payload():
    model = RelationshipRequest(
        target={"machine_id": 1, "tag_id": 123},
        start_utc=datetime(2026, 6, 11, 0, 0, 0, tzinfo=timezone.utc),
        end_utc=datetime(2026, 6, 12, 0, 0, 0, tzinfo=timezone.utc),
        bucket_seconds=60,
        max_points_per_series=2000,
        candidate_scope="same_machine",
        max_candidate_tags=300,
        max_results=25,
        min_pair_count=30,
        max_lag_seconds=1800,
    )
    assert model.target.tag_id == 123
    assert model.resolved_bucket_seconds() == 60


def test_relationship_request_rejects_invalid_date_range():
    with pytest.raises(ValidationError):
        RelationshipRequest(
            target={"machine_id": 1, "tag_id": 123},
            start_utc=datetime(2026, 6, 12, 0, 0, 0, tzinfo=timezone.utc),
            end_utc=datetime(2026, 6, 11, 0, 0, 0, tzinfo=timezone.utc),
            bucket_seconds=60,
            max_points_per_series=2000,
            candidate_scope="same_machine",
        )


def test_relationship_request_requires_candidate_ids_for_selected_tags():
    with pytest.raises(ValidationError):
        RelationshipRequest(
            target={"machine_id": 1, "tag_id": 123},
            start_utc=datetime(2026, 6, 11, 0, 0, 0, tzinfo=timezone.utc),
            end_utc=datetime(2026, 6, 12, 0, 0, 0, tzinfo=timezone.utc),
            bucket_seconds=60,
            max_points_per_series=2000,
            candidate_scope="selected_tags",
            candidate_tag_ids=[],
        )


def test_relationship_request_enforces_max_results_bounds():
    with pytest.raises(ValidationError):
        RelationshipRequest(
            target={"machine_id": 1, "tag_id": 123},
            start_utc=datetime(2026, 6, 11, 0, 0, 0, tzinfo=timezone.utc),
            end_utc=datetime(2026, 6, 12, 0, 0, 0, tzinfo=timezone.utc),
            bucket_seconds=60,
            max_points_per_series=2000,
            candidate_scope="same_machine",
            max_results=101,
        )


def test_relationship_request_rejects_max_lag_over_one_day():
    with pytest.raises(ValidationError):
        RelationshipRequest(
            target={"machine_id": 1, "tag_id": 123},
            start_utc=datetime(2026, 6, 11, 0, 0, 0, tzinfo=timezone.utc),
            end_utc=datetime(2026, 6, 12, 0, 0, 0, tzinfo=timezone.utc),
            bucket_seconds=60,
            max_points_per_series=2000,
            candidate_scope="same_machine",
            max_lag_seconds=86401,
        )


def test_relationship_request_enforces_max_points_bounds():
    with pytest.raises(ValidationError):
        RelationshipRequest(
            target={"machine_id": 1, "tag_id": 123},
            start_utc=datetime(2026, 6, 11, 0, 0, 0, tzinfo=timezone.utc),
            end_utc=datetime(2026, 6, 12, 0, 0, 0, tzinfo=timezone.utc),
            bucket_seconds=60,
            max_points_per_series=99,
            candidate_scope="same_machine",
        )
    with pytest.raises(ValidationError):
        RelationshipRequest(
            target={"machine_id": 1, "tag_id": 123},
            start_utc=datetime(2026, 6, 11, 0, 0, 0, tzinfo=timezone.utc),
            end_utc=datetime(2026, 6, 12, 0, 0, 0, tzinfo=timezone.utc),
            bucket_seconds=60,
            max_points_per_series=10001,
            candidate_scope="same_machine",
        )
