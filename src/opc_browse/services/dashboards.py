from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4


ALLOWED_PANEL_TYPES = {"timeseries", "relationship_results", "tag_profile"}


def sanitize_dashboard_id(value: str) -> str:
    sanitized = re.sub(r"[^a-z0-9_-]+", "-", (value or "").strip().lower())
    sanitized = re.sub(r"-{2,}", "-", sanitized).strip("-_")
    return sanitized or "dashboard"


def new_dashboard_id(name: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{sanitize_dashboard_id(name)}-{timestamp}"


def dashboard_path(dashboard_id: str, storage_dir: str | Path = "dashboards") -> Path:
    safe_id = sanitize_dashboard_id(dashboard_id)
    return Path(storage_dir) / f"{safe_id}.json"


def default_panel_layout(index: int) -> dict:
    return {
        "x": 0,
        "y": max(index, 0) * 4,
        "w": 12,
        "h": 4,
    }


def validate_panel_layout(layout) -> dict:
    if not isinstance(layout, dict):
        raise ValueError("Panel layout must be an object")

    x = int(layout.get("x", 0))
    y = int(layout.get("y", 0))
    w = int(layout.get("w", 12))
    h = int(layout.get("h", 4))

    if x < 0 or x > 11:
        raise ValueError("Panel layout x must be between 0 and 11")
    if y < 0:
        raise ValueError("Panel layout y must be >= 0")
    if w < 1 or w > 12:
        raise ValueError("Panel layout w must be between 1 and 12")
    if x + w > 12:
        raise ValueError("Panel layout x + w must be <= 12")
    if h < 2:
        raise ValueError("Panel layout h must be >= 2")

    return {"x": x, "y": y, "w": w, "h": h}


def panel_sort_key(panel) -> tuple[int, int, str]:
    layout = panel.get("layout") or {}
    return (
        int(layout.get("y", 0)),
        int(layout.get("x", 0)),
        str(panel.get("id") or ""),
    )


def normalize_panel_layouts(panels) -> list[dict]:
    normalized = []
    next_row = 0
    for index, panel in enumerate(panels):
        panel_copy = dict(panel)
        layout = panel_copy.get("layout")
        if layout is None:
            layout = default_panel_layout(next_row)
            next_row += layout["h"]
        else:
            layout = validate_panel_layout(layout)
            next_row = max(next_row, layout["y"] + layout["h"])

        refresh = panel_copy.get("refresh") or {}
        if not isinstance(refresh, dict):
            raise ValueError("Panel refresh metadata must be an object")
        mode = str(refresh.get("mode") or "manual").strip() or "manual"
        if mode != "manual":
            raise ValueError("Panel refresh mode must be manual")

        panel_copy["layout"] = layout
        panel_copy["refresh"] = {
            "mode": "manual",
            "last_refreshed_utc": refresh.get("last_refreshed_utc"),
        }
        normalized.append(panel_copy)

    return sorted(normalized, key=panel_sort_key)


def _jsonable(value: Any) -> Any:
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
    return value


def validate_dashboard_payload(payload) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Dashboard payload must be an object")

    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("Dashboard name is required")

    workspace = payload.get("workspace") or {}
    if not isinstance(workspace, dict):
        raise ValueError("Dashboard workspace must be an object")

    panels = payload.get("panels") or []
    if not isinstance(panels, list):
        raise ValueError("Dashboard panels must be a list")

    validated_panels = []
    for panel in panels:
        if not isinstance(panel, dict):
            raise ValueError("Each panel must be an object")
        panel_id = str(panel.get("id") or "").strip() or f"panel_{uuid4().hex[:8]}"
        panel_type = str(panel.get("type") or "").strip()
        title = str(panel.get("title") or "").strip()
        if panel_type not in ALLOWED_PANEL_TYPES:
            raise ValueError(f"Unsupported panel type: {panel_type}")
        if not title:
            raise ValueError("Each panel requires a title")
        settings = panel.get("settings") or {}
        if not isinstance(settings, dict):
            raise ValueError("Panel settings must be an object")
        series = panel.get("series") or []
        if not isinstance(series, list):
            raise ValueError("Panel series must be a list")
        data = panel.get("data") or {}
        if not isinstance(data, dict):
            raise ValueError("Panel data must be an object")

        if panel_type == "timeseries":
            if not series:
                raise ValueError("Timeseries panels require at least one series")
            for series_item in series:
                if not isinstance(series_item, dict):
                    raise ValueError("Timeseries series items must be objects")
                if "machine_id" not in series_item or "tag_id" not in series_item:
                    raise ValueError("Timeseries series items require machine_id and tag_id")
        elif panel_type == "relationship_results":
            request_payload = settings.get("request")
            if not isinstance(request_payload, dict):
                raise ValueError("Relationship results panels require request settings")
        elif panel_type == "tag_profile":
            if "machine_id" not in settings or "tag_id" not in settings:
                raise ValueError("Tag profile panels require machine_id and tag_id in settings")

        validated_panels.append(
            {
                "id": sanitize_dashboard_id(panel_id),
                "type": panel_type,
                "title": title,
                "layout": panel.get("layout"),
                "refresh": panel.get("refresh"),
                "settings": _jsonable(settings),
                "series": _jsonable(series),
                "data": _jsonable(data),
            }
        )

    raw_dashboard_id = str(payload.get("id") or "").strip()

    return {
        "id": sanitize_dashboard_id(raw_dashboard_id) if raw_dashboard_id else None,
        "name": name,
        "description": str(payload.get("description") or ""),
        "created_at_utc": payload.get("created_at_utc"),
        "updated_at_utc": payload.get("updated_at_utc"),
        "workspace": _jsonable(workspace),
        "panels": normalize_panel_layouts(validated_panels),
    }


def list_dashboards(storage_dir) -> list[dict]:
    storage_path = Path(storage_dir)
    if not storage_path.exists():
        return []

    dashboards = []
    for path in storage_path.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        dashboards.append(
            {
                "id": payload.get("id"),
                "name": payload.get("name"),
                "description": payload.get("description", ""),
                "created_at_utc": payload.get("created_at_utc"),
                "updated_at_utc": payload.get("updated_at_utc"),
                "panel_count": len(payload.get("panels", [])),
            }
        )
    dashboards.sort(key=lambda item: item.get("updated_at_utc") or "", reverse=True)
    return dashboards


def load_dashboard(dashboard_id, storage_dir) -> dict:
    path = dashboard_path(dashboard_id, storage_dir)
    if not path.exists():
        raise FileNotFoundError(dashboard_id)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return validate_dashboard_payload(payload)


def save_dashboard(payload, storage_dir) -> dict:
    validated = validate_dashboard_payload(payload)
    storage_path = Path(storage_dir)
    storage_path.mkdir(parents=True, exist_ok=True)

    dashboard_id = validated["id"] or new_dashboard_id(validated["name"])
    existing = None
    path = dashboard_path(dashboard_id, storage_path)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))

    now = datetime.now(timezone.utc).isoformat()
    result = {
        "id": dashboard_id,
        "name": validated["name"],
        "description": validated["description"],
        "created_at_utc": (existing or {}).get("created_at_utc") or validated["created_at_utc"] or now,
        "updated_at_utc": now,
        "workspace": validated["workspace"],
        "panels": validated["panels"],
    }

    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    temp_path.replace(path)
    return result


def delete_dashboard(dashboard_id, storage_dir) -> bool:
    path = dashboard_path(dashboard_id, storage_dir)
    if not path.exists():
        return False
    path.unlink()
    return True
