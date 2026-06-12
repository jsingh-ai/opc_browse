import asyncio
import json

from starlette.routing import Mount

from opc_browse.main import app


async def call_asgi(app, method: str, path: str):
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": [(b"host", b"testserver")],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }
    messages = []
    sent = False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)

    await app(scope, receive, send)
    start = next(message for message in messages if message["type"] == "http.response.start")
    body = b"".join(
        message.get("body", b"") for message in messages if message["type"] == "http.response.body"
    )
    headers = {key.decode("utf-8"): value.decode("utf-8") for key, value in start["headers"]}
    return start["status"], headers, body


def test_root_route_returns_html():
    status_code, headers, body = asyncio.run(call_asgi(app, "GET", "/"))
    assert status_code == 200
    assert "text/html" in headers["content-type"]
    assert b"OPC Browse Data Explorer" in body
    assert b"/static/js/explorer.js" in body
    assert b"Saved Dashboards" in body


def test_static_files_mount_exists():
    assert any(
        isinstance(route, Mount) and route.path == "/static"
        for route in app.routes
    )
