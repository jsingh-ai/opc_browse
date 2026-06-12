import asyncio
import json
from pathlib import Path

from opc_browse.main import app
from opc_browse.routers import dashboards as dashboards_router


class DummySettings:
    def __init__(self, dashboard_storage_dir):
        self.dashboard_storage_dir = str(dashboard_storage_dir)


async def call_asgi_json(app, method: str, path: str, payload: dict | None = None):
    body = json.dumps(payload).encode("utf-8") if payload is not None else b""
    headers = [(b"host", b"testserver")]
    if body:
        headers.extend(
            [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("utf-8")),
            ]
        )
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }
    messages = []
    request_sent = False

    async def receive():
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)

    await app(scope, receive, send)

    status_code = next(message["status"] for message in messages if message["type"] == "http.response.start")
    response_body = b"".join(
        message.get("body", b"") for message in messages if message["type"] == "http.response.body"
    )
    return status_code, json.loads(response_body.decode("utf-8"))


def test_create_list_get_delete_dashboard(tmp_path, monkeypatch):
    monkeypatch.setattr(
        dashboards_router,
        "get_settings",
        lambda: DummySettings(tmp_path),
    )
    payload = {
        "name": "Line Dashboard",
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

    create_status, created = asyncio.run(call_asgi_json(app, "POST", "/api/dashboards", payload))
    assert create_status == 200
    dashboard_id = created["id"]

    list_status, listed = asyncio.run(call_asgi_json(app, "GET", "/api/dashboards"))
    assert list_status == 200
    assert listed["dashboards"][0]["id"] == dashboard_id

    get_status, loaded = asyncio.run(call_asgi_json(app, "GET", f"/api/dashboards/{dashboard_id}"))
    assert get_status == 200
    assert loaded["name"] == "Line Dashboard"

    delete_status, deleted = asyncio.run(call_asgi_json(app, "DELETE", f"/api/dashboards/{dashboard_id}"))
    assert delete_status == 200
    assert deleted["deleted"] is True
