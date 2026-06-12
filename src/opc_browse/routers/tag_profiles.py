from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from opc_browse.db import connection_context
from opc_browse.models import TagProfileSummary, TagProfilesResponse
from opc_browse.services.tag_profile_queries import (
    fetch_machine_tag_profiles,
    fetch_tag_profile_stats,
)
from opc_browse.services.tag_scoring import classify_stale
from opc_browse.services.time_utils import normalize_datetime_to_utc_naive_for_mysql


router = APIRouter(tags=["tag_profiles"])


@router.get(
    "/machines/{machine_id}/tags/profiles",
    response_model=TagProfilesResponse,
)
def get_machine_tag_profiles(
    machine_id: int,
    start_utc: datetime | None = Query(default=None),
    end_utc: datetime | None = Query(default=None),
    search: str | None = None,
    numeric_only: bool = False,
    limit: int = Query(default=1000, ge=1, le=5000),
    grade: str | None = Query(default=None),
    semantic_type: str | None = Query(default=None),
    active_only: bool = False,
    order_by: str = Query(default="score", pattern="^(score|last_seen|sample_count|display_name)$"),
):
    with connection_context() as connection:
        profiles = fetch_machine_tag_profiles(
            connection,
            machine_id=machine_id,
            start_utc=normalize_datetime_to_utc_naive_for_mysql(start_utc),
            end_utc=normalize_datetime_to_utc_naive_for_mysql(end_utc),
            search=search,
            numeric_only=numeric_only,
            limit=limit,
            order_by=order_by,
        )

    filtered = profiles
    if grade:
        filtered = [
            item for item in filtered if item.get("usefulness_score", {}).get("grade") == grade
        ]
    if semantic_type:
        filtered = [
            item
            for item in filtered
            if item.get("usefulness_score", {}).get("semantic_type") == semantic_type
        ]
    if active_only:
        filtered = [
            item
            for item in filtered
            if item.get("usefulness_score", {}).get("grade") != "ignore"
            and not classify_stale(item.get("last_seen_utc"), datetime.utcnow())
        ]

    return TagProfilesResponse(
        machine_id=machine_id,
        count=len(filtered),
        profiles=[TagProfileSummary(**item) for item in filtered],
    )


@router.get(
    "/machines/{machine_id}/tags/{tag_id}/scored-profile",
    response_model=TagProfileSummary,
)
def get_scored_tag_profile(
    machine_id: int,
    tag_id: int,
    start_utc: datetime | None = Query(default=None),
    end_utc: datetime | None = Query(default=None),
):
    with connection_context() as connection:
        profile = fetch_tag_profile_stats(
            connection,
            machine_id=machine_id,
            tag_id=tag_id,
            start_utc=normalize_datetime_to_utc_naive_for_mysql(start_utc),
            end_utc=normalize_datetime_to_utc_naive_for_mysql(end_utc),
        )
    if not profile:
        raise HTTPException(status_code=404, detail="Tag scored profile not found")
    return TagProfileSummary(**profile)
