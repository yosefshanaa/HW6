"""Thief MCP server entry point (run with ``uv run --extra mcp ...``)."""

from __future__ import annotations

from cop_thief.mcp.server_app import build_app
from cop_thief.shared.config import load_config


def main() -> None:
    """Launch the Thief FastMCP server on its configured host/port."""
    config = load_config()
    app = build_app("thief", config)
    app.run(transport="http", host=config.get("mcp.thief_host"), port=config.get("mcp.thief_port"))


if __name__ == "__main__":
    main()
