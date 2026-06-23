"""End-to-end check that bearer auth is *enforced* on the live FastMCP HTTP app.

Requires the ``mcp`` extra (``uv sync --extra mcp``); the whole module is skipped otherwise so
the default test run / CI (which installs no extras) stays green. The token-less passthrough
(``bearer_middleware(None) == []``) is covered unconditionally in ``test_serve.py``.
"""

from __future__ import annotations

import pytest

from cop_thief.mcp.asgi_auth import bearer_middleware

fastmcp = pytest.importorskip("fastmcp")
pytest.importorskip("starlette")

from starlette.testclient import TestClient  # noqa: E402


def _client(expected: str | None) -> TestClient:
    app = fastmcp.FastMCP("test-auth")

    @app.tool
    def health_check() -> dict:
        return {"ok": True}

    return TestClient(app.http_app(middleware=bearer_middleware(expected)))


def test_missing_token_is_rejected():
    with _client("s3cret") as client:
        assert client.post("/mcp/").status_code == 401


def test_bad_token_is_rejected():
    with _client("s3cret") as client:
        resp = client.post("/mcp/", headers={"Authorization": "Bearer wrong"})
        assert resp.status_code == 401


def test_valid_token_passes_the_gate():
    with _client("s3cret") as client:
        resp = client.post(
            "/mcp/",
            headers={
                "Authorization": "Bearer s3cret",
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
        )
        # The bearer gate let it through to the MCP layer (which handles the body itself).
        assert resp.status_code != 401


def test_auth_disabled_when_no_token_configured():
    with _client(None) as client:
        assert client.post("/mcp/").status_code != 401
