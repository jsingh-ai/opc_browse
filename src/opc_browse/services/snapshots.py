from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _jsonable(value.model_dump())
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, Path):
        return str(value)
    return value


def relationship_response_to_jsonable(payload) -> dict:
    return _jsonable(payload)


def default_snapshot_path(machine_id: int, tag_id: int, base_dir: str = "snapshots") -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(base_dir) / f"relationship_{machine_id}_{tag_id}_{timestamp}.json"


def load_snapshot(path) -> dict:
    snapshot_path = Path(path)
    return json.loads(snapshot_path.read_text(encoding="utf-8"))


def compare_snapshots(snapshot_a, snapshot_b, top: int = 20) -> dict:
    payload_a = relationship_response_to_jsonable(snapshot_a)
    payload_b = relationship_response_to_jsonable(snapshot_b)

    results_a = {item.get("tag_id"): item for item in payload_a.get("results", []) if item.get("tag_id") is not None}
    results_b = {item.get("tag_id"): item for item in payload_b.get("results", []) if item.get("tag_id") is not None}

    tags_a = set(results_a)
    tags_b = set(results_b)
    added_tag_ids = sorted(tags_b - tags_a)
    removed_tag_ids = sorted(tags_a - tags_b)
    common_tag_ids = sorted(tags_a & tags_b)

    score_changes = []
    relationship_type_changes = []
    for tag_id in common_tag_ids:
        row_a = results_a[tag_id]
        row_b = results_b[tag_id]
        score_a = float(row_a.get("score") or 0.0)
        score_b = float(row_b.get("score") or 0.0)
        delta = score_b - score_a
        score_changes.append(
            {
                "tag_id": tag_id,
                "display_name": row_b.get("display_name") or row_a.get("display_name"),
                "opc_path": row_b.get("opc_path") or row_a.get("opc_path"),
                "score_a": score_a,
                "score_b": score_b,
                "score_delta": delta,
            }
        )
        relationship_a = row_a.get("relationship_type")
        relationship_b = row_b.get("relationship_type")
        if relationship_a != relationship_b:
            relationship_type_changes.append(
                {
                    "tag_id": tag_id,
                    "display_name": row_b.get("display_name") or row_a.get("display_name"),
                    "relationship_type_a": relationship_a,
                    "relationship_type_b": relationship_b,
                }
            )

    score_changes.sort(key=lambda item: abs(item["score_delta"]), reverse=True)

    return {
        "snapshot_a": {
            "target": payload_a.get("target", {}),
            "window": payload_a.get("window", {}),
            "analysis": payload_a.get("analysis", {}),
            "result_count": len(payload_a.get("results", [])),
        },
        "snapshot_b": {
            "target": payload_b.get("target", {}),
            "window": payload_b.get("window", {}),
            "analysis": payload_b.get("analysis", {}),
            "result_count": len(payload_b.get("results", [])),
        },
        "added_tag_ids": added_tag_ids,
        "removed_tag_ids": removed_tag_ids,
        "common_tag_ids": common_tag_ids,
        "score_changes": score_changes[:top],
        "relationship_type_changes": relationship_type_changes[:top],
    }
