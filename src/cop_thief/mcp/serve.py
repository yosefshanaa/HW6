"""Run a deployed MCP server with cloud-friendly binding + enforced bearer auth.

``resolve_bind`` is pure and unit-tested; ``run_server`` is the thin FastMCP glue (lazy
imports, excluded from coverage) shared by the cop and thief entry points.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from cop_thief.shared.config import load_config


def resolve_bind(config, role: str, environ: Mapping[str, str]) -> tuple[str, int]:
    """Resolve the ``(host, port)`` to bind for ``role``.

    Cloud platforms (Cloud Run, Fly, Render, …) inject ``$PORT`` and expect the process to
    listen on all interfaces, so when ``PORT`` is set we bind ``0.0.0.0`` to it. Otherwise we
    use the configured ``mcp.<role>_host`` / ``mcp.<role>_port`` for local runs.
    """
    port = environ.get("PORT")
    if port:
        return "0.0.0.0", int(port)
    return config.get(f"mcp.{role}_host"), int(config.get(f"mcp.{role}_port"))


def run_server(role: str, config=None) -> None:  # pragma: no cover - FastMCP server glue
    """Build the FastMCP app for ``role`` and serve it over HTTP with bearer enforcement."""
    from cop_thief.mcp.asgi_auth import bearer_middleware
    from cop_thief.mcp.auth import load_expected_token
    from cop_thief.mcp.server_app import build_app

    config = config or load_config()
    app = build_app(role, config)
    host, port = resolve_bind(config, role, os.environ)
    middleware = bearer_middleware(load_expected_token(config))
    app.run(transport="http", host=host, port=port, middleware=middleware)
