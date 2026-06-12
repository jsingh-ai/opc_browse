import json

import pytest

from opc_browse.services.dashboards import (
    default_panel_layout,
    dashboard_path,
    delete_dashboard,
    list_dashboards,
    load_dashboard,
    panel_sort_key,
    sanitize_dashboard_id,
    save_dashboard,
    validate_dashboard_payload,
)


def test_sanitize_dashboard_id_removes_path_traversal_chars():
    assert sanitize_dashboard_id("../../My Dashboard") == "my-dashboard"


def test_save_load_list_delete_dashboard(tmp_path):
    payload = {
        "name": "Speed vs Vacuum",
        "description": "",
        "workspace": {
            "machine_id": 1,
            "start_utc": "2026-06-11T00:00:00Z",
            "end_utc": "2026-06-12T00:00:00Z",
            "bucket_seconds": 60,
        },
        "panels": [
            {
                "id": "panel_1",
                "type": "timeseries",
                "title": "Trend",
                "settings": {"aggregation": "avg", "chart_mode": "raw"},
                "series": [{"machine_id": 1, "tag_id": 123, "label": "Target"}],
            }
        ],
    }
    saved = save_dashboard(payload, tmp_path)
    loaded = load_dashboard(saved["id"], tmp_path)
    listed = list_dashboards(tmp_path)

    assert loaded["id"] == saved["id"]
    assert listed[0]["id"] == saved["id"]
    assert delete_dashboard(saved["id"], tmp_path) is True
    assert list_dashboards(tmp_path) == []


def test_dashboard_path_stays_under_storage_dir(tmp_path):
    path = dashboard_path("../escape", tmp_path)
    assert path.parent == tmp_path
    assert path.name == "escape.json"


def test_validation_rejects_missing_name_or_invalid_panels():
    with pytest.raises(ValueError):
        validate_dashboard_payload({"name": "", "panels": []})
    with pytest.raises(ValueError):
        validate_dashboard_payload(
            {
                "name": "Bad",
                "workspace": {},
                "panels": [{"type": "timeseries", "title": "Missing series"}],
            }
        )


def test_old_panel_without_layout_gets_default_layout_and_refresh():
    payload = validate_dashboard_payload(
        {
            "name": "Legacy",
            "workspace": {},
            "panels": [
                {
                    "id": "panel_1",
                    "type": "timeseries",
                    "title": "Trend",
                    "settings": {"aggregation": "avg"},
                    "series": [{"machine_id": 1, "tag_id": 123}],
                }
            ],
        }
    )
    panel = payload["panels"][0]
    assert panel["layout"] == default_panel_layout(0)
    assert panel["refresh"] == {"mode": "manual", "last_refreshed_utc": None}


def test_invalid_layout_rejects_x_plus_w_above_12():
    with pytest.raises(ValueError):
        validate_dashboard_payload(
            {
                "name": "Bad Layout",
                "workspace": {},
                "panels": [
                    {
                        "id": "panel_1",
                        "type": "timeseries",
                        "title": "Trend",
                        "layout": {"x": 8, "y": 0, "w": 5, "h": 4},
                        "settings": {"aggregation": "avg"},
                        "series": [{"machine_id": 1, "tag_id": 123}],
                    }
                ],
            }
        )


def test_invalid_layout_rejects_height_below_two():
    with pytest.raises(ValueError):
        validate_dashboard_payload(
            {
                "name": "Bad Height",
                "workspace": {},
                "panels": [
                    {
                        "id": "panel_1",
                        "type": "timeseries",
                        "title": "Trend",
                        "layout": {"x": 0, "y": 0, "w": 12, "h": 1},
                        "settings": {"aggregation": "avg"},
                        "series": [{"machine_id": 1, "tag_id": 123}],
                    }
                ],
            }
        )


def test_panel_sort_key_orders_by_y_then_x():
    panels = [
        {"id": "c", "layout": {"x": 2, "y": 5, "w": 4, "h": 4}},
        {"id": "a", "layout": {"x": 1, "y": 0, "w": 4, "h": 4}},
        {"id": "b", "layout": {"x": 0, "y": 5, "w": 4, "h": 4}},
    ]
    ordered = sorted(panels, key=panel_sort_key)
    assert [panel["id"] for panel in ordered] == ["a", "b", "c"]


def test_validation_accepts_kpi_panel_settings():
    payload = validate_dashboard_payload(
        {
            "name": "KPI Dashboard",
            "workspace": {},
            "panels": [
                {
                    "id": "panel_1",
                    "type": "kpi",
                    "title": "Speed KPI",
                    "settings": {"machine_id": 1, "tag_id": 123},
                    "series": [],
                }
            ],
        }
    )
    assert payload["panels"][0]["type"] == "kpi"
