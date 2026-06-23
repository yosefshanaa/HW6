"""Unit tests for cloud-friendly MCP bind resolution (``mcp.serve.resolve_bind``)."""

from __future__ import annotations

from cop_thief.mcp.asgi_auth import bearer_middleware
from cop_thief.mcp.serve import resolve_bind


class _Cfg:
    """Minimal config stub exposing ``get(key, default)`` like the real loader."""

    def __init__(self, values: dict) -> None:
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


def test_port_env_binds_all_interfaces():
    cfg = _Cfg({"mcp.cop_host": "127.0.0.1", "mcp.cop_port": 8001})
    assert resolve_bind(cfg, "cop", {"PORT": "8080"}) == ("0.0.0.0", 8080)


def test_falls_back_to_configured_host_port_without_port_env():
    cfg = _Cfg({"mcp.thief_host": "127.0.0.1", "mcp.thief_port": 8002})
    assert resolve_bind(cfg, "thief", {}) == ("127.0.0.1", 8002)


def test_empty_port_env_is_ignored():
    cfg = _Cfg({"mcp.cop_host": "127.0.0.1", "mcp.cop_port": 8001})
    assert resolve_bind(cfg, "cop", {"PORT": ""}) == ("127.0.0.1", 8001)


def test_no_token_yields_no_enforcement_middleware():
    # Needs neither FastMCP nor Starlette: an empty token means "auth disabled".
    assert bearer_middleware(None) == []
    assert bearer_middleware("") == []
