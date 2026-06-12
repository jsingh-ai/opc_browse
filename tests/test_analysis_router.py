import asyncio
import json
from contextlib import contextmanager

from opc_browse.main import app
from opc_browse.routers import analysis as analysis_router


@contextmanager
def dummy_connection_context():
    yield object()


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


def test_post_analysis_relationships_returns_expected_shape(monkeypatch):
    def fake_run_relationship_analysis(connection, payload):
        return {
            "target": {
                "machine_id": 1,
                "tag_id": 123,
                "label": "Target",
                "opc_path": "Area/Target",
                "display_name": "Target",
                "data_type": "Double",
            },
            "window": {
                "start_utc": "2026-06-11T00:00:00+00:00",
                "end_utc": "2026-06-12T00:00:00+00:00",
                "requested_bucket_seconds": 60,
                "actual_bucket_seconds": 120,
            },
            "analysis": {
                "method": "stats_v1",
                "candidate_scope": "same_machine",
                "candidate_count_scanned": 10,
                "candidate_count_analyzed": 3,
                "skipped_count": 2,
                "skipped_by_reason": {"insufficient_pair_count": 2},
                "max_lag_seconds": 1800,
                "min_pair_count": 30,
                "warnings": [
                    "actual bucket_seconds was increased from 60 to 120 to respect max_points_per_series"
                ],
            },
            "results": [
                {
                    "machine_id": 1,
                    "tag_id": 456,
                    "label": "Candidate",
                    "opc_path": "Area/Candidate",
                    "display_name": "Candidate",
                    "data_type": "Double",
                    "relationship_type": "possible_driver",
                    "score": 0.91,
                    "same_time_corr": 0.7,
                    "delta_corr": 0.8,
                    "best_lag_corr": 0.91,
                    "best_lag_seconds": 300,
                    "pair_count": 120,
                    "direction": "positive",
                    "notes": ["candidate leads target by 300 seconds"],
                }
            ],
            "skipped": [{"tag_id": 789, "reason": "insufficient_pair_count"}],
        }

    monkeypatch.setattr(analysis_router, "connection_context", dummy_connection_context)
    monkeypatch.setattr(analysis_router, "run_relationship_analysis", fake_run_relationship_analysis)

    status_code, payload = asyncio.run(
        call_asgi_json(
            app,
            "POST",
            "/api/analysis/relationships",
            {
                "target": {"machine_id": 1, "tag_id": 123},
                "start_utc": "2026-06-11T00:00:00Z",
                "end_utc": "2026-06-12T00:00:00Z",
                "bucket_seconds": 60,
                "max_points_per_series": 2000,
                "candidate_scope": "same_machine",
                "max_candidate_tags": 300,
                "max_results": 25,
                "min_pair_count": 30,
                "max_lag_seconds": 1800,
            },
        )
    )

    assert status_code == 200
    assert "target" in payload
    assert "window" in payload
    assert "analysis" in payload
    assert "results" in payload
    assert "skipped" in payload
    assert payload["analysis"]["skipped_count"] == 2
    assert payload["analysis"]["skipped_by_reason"] == {"insufficient_pair_count": 2}
    assert payload["analysis"]["warnings"]


def test_post_analysis_relationships_rejects_selected_tags_without_candidate_ids():
    status_code, payload = asyncio.run(
        call_asgi_json(
            app,
            "POST",
            "/api/analysis/relationships",
            {
                "target": {"machine_id": 1, "tag_id": 123},
                "start_utc": "2026-06-11T00:00:00Z",
                "end_utc": "2026-06-12T00:00:00Z",
                "bucket_seconds": 60,
                "max_points_per_series": 2000,
                "candidate_scope": "selected_tags",
                "candidate_tag_ids": [],
                "max_candidate_tags": 300,
                "max_results": 25,
                "min_pair_count": 30,
                "max_lag_seconds": 1800,
            },
        )
    )
    assert status_code == 422
    assert payload["detail"]


def test_get_analysis_methods_returns_supported_options():
    status_code, payload = asyncio.run(call_asgi_json(app, "GET", "/api/analysis/methods"))
    assert status_code == 200
    assert payload["methods"] == ["stats_v1"]
    assert "same_machine" in payload["candidate_scopes"]
