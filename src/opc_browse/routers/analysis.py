from __future__ import annotations

from fastapi import APIRouter, HTTPException

from opc_browse.db import connection_context
from opc_browse.models import RelationshipRequest, RelationshipResponse
from opc_browse.services.relationship_analysis import run_relationship_analysis


router = APIRouter(tags=["analysis"])


@router.get("/analysis/methods")
async def get_analysis_methods():
    return {
        "methods": ["stats_v1"],
        "relationship_types": [
            "moves_together",
            "possible_driver",
            "possible_effect",
            "changes_together",
        ],
        "candidate_scopes": ["same_machine", "same_folder", "selected_tags"],
        "notes": [
            "Correlations are exploratory and do not prove causation.",
            "Positive best_lag_seconds means the candidate leads the target.",
            "Negative best_lag_seconds means the candidate follows the target.",
        ],
    }


@router.post("/analysis/relationships", response_model=RelationshipResponse)
async def analyze_tag_relationships(payload: RelationshipRequest):
    with connection_context() as connection:
        try:
            return RelationshipResponse(**run_relationship_analysis(connection, payload))
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
