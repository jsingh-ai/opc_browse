import asyncio

from starlette.routing import Mount

from opc_browse.main import STATIC_DIR, app


def test_root_route_returns_html():
    async def request_root():
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
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

    status_code, headers, body = asyncio.run(request_root())
    assert status_code == 200
    assert "text/html" in headers["content-type"]
    assert b"OPC Browse Data Explorer" in body
    assert b"/static/css/explorer.css" in body
    assert b"/static/js/explorer.js" in body
    assert b"Choose a machine and target tag" in body
    assert b"Use scored profiles" in body
    assert b"toast-container" in body


def test_static_files_mount_exists():
    assert any(
        isinstance(route, Mount) and route.path == "/static"
        for route in app.routes
    )


def test_static_css_route_returns_css():
    css_path = STATIC_DIR / "css" / "explorer.css"
    assert css_path.exists()
    assert "Theme Variables" in css_path.read_text(encoding="utf-8")


def test_static_js_route_returns_javascript():
    js_path = STATIC_DIR / "js" / "explorer.js"
    assert js_path.exists()
    assert "showToast" in js_path.read_text(encoding="utf-8")
