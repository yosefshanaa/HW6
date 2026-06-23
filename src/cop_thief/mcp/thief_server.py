"""Thief MCP server entry point (run with ``uv run --extra mcp ...``)."""

from __future__ import annotations

from cop_thief.mcp.serve import run_server


def main() -> None:
    """Launch the Thief FastMCP server over HTTP with enforced bearer auth."""
    run_server("thief")


if __name__ == "__main__":
    main()
