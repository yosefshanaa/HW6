"""MCP client wrapper + transports (PLAN §8, PRD_mcp_servers §2.3).

``AgentClient`` talks to one server's tools through a ``Transport``. Two transports
are provided: ``InProcessTransport`` binds directly to a referee + inbox (so the
client/server tool path is contract-testable without a network), and
``HttpTransport`` reaches a *remote* MCP server over HTTP with bearer auth — the
path used for the cross-team bonus match. Both honour the same interface, so the
match machinery is transport-agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from cop_thief.engine.referee import Referee
from cop_thief.mcp import tools


class Transport(ABC):
    """Calls a named tool with keyword arguments, returning a JSON-ready dict."""

    @abstractmethod
    def call(self, tool: str, **kwargs: Any) -> dict[str, Any]:
        """Invoke ``tool`` and return its result."""


class InProcessTransport(Transport):
    """Dispatches tool calls to :mod:`cop_thief.mcp.tools` against one referee."""

    def __init__(self, referee: Referee) -> None:
        self.referee = referee
        self.inbox: list[dict[str, str]] = []

    def call(self, tool: str, **kwargs: Any) -> dict[str, Any]:
        if tool == "health_check":
            return tools.health_check()
        if tool == "get_observation":
            return tools.get_observation(self.referee, kwargs["role"])
        if tool == "validate_action":
            return tools.validate_action(self.referee, kwargs["role"], kwargs["action"])
        if tool == "submit_turn":
            return tools.submit_turn(self.referee, kwargs["payload"])
        if tool == "receive_message":
            return tools.receive_message(self.inbox, kwargs["from_role"], kwargs["message"])
        if tool == "get_match_status":
            return tools.get_match_status(self.referee)
        if tool == "get_messages":
            return tools.get_messages(self.inbox)
        if tool == "reset":
            self.inbox.clear()
            return tools.reset(self.referee, kwargs["cop"], kwargs["thief"])
        raise ValueError(f"unknown tool: {tool}")


# The remote server is role-bound (one server per role), so role-scoped tools take
# no ``role`` argument over the wire — only these keys are forwarded per tool.
_HTTP_TOOL_ARGS: dict[str, tuple[str, ...]] = {
    "health_check": (),
    "get_observation": (),
    "validate_action": ("action",),
    "submit_turn": ("payload",),
    "receive_message": ("from_role", "message"),
    "get_match_status": (),
    "get_messages": (),
    "reset": ("cop", "thief"),
}


class HttpTransport(Transport):
    """Calls a remote MCP server over HTTP (bearer auth) via the FastMCP client.

    ``target`` is the server URL for a real match, or a FastMCP app object for
    in-memory tests (no socket). A persistent event loop keeps one client session
    open across the sub-game's turns. ``fastmcp`` is imported lazily (the optional
    ``mcp`` extra), so the core package never requires it.
    """

    def __init__(self, target: Any, *, token: str | None = None, timeout: float = 30.0) -> None:
        import asyncio

        from fastmcp import Client

        self._loop = asyncio.new_event_loop()
        if isinstance(target, str):
            # Strip a trailing slash: FastMCP serves at ``/mcp`` and a request to
            # ``/mcp/`` 307-redirects, on which httpx drops the Authorization header
            # → a spurious 401. Normalising here makes either URL form work.
            target = target.rstrip("/")
        if isinstance(target, str) and token:
            from fastmcp.client.auth import BearerAuth

            client = Client(target, auth=BearerAuth(token), timeout=timeout)
        else:
            client = Client(target, timeout=timeout)
        self._client = client
        self._loop.run_until_complete(client.__aenter__())

    def call(self, tool: str, **kwargs: Any) -> dict[str, Any]:
        keys = _HTTP_TOOL_ARGS.get(tool)
        if keys is None:
            raise ValueError(f"unknown tool: {tool}")
        args = {k: kwargs[k] for k in keys}
        result = self._loop.run_until_complete(self._client.call_tool(tool, args))
        return result.data

    def close(self) -> None:
        """Close the client session and its event loop (call after the sub-game)."""
        try:
            self._loop.run_until_complete(self._client.__aexit__(None, None, None))
        finally:
            self._loop.close()


class AgentClient:
    """Convenience wrapper over a transport for one role."""

    def __init__(self, transport: Transport, role: str) -> None:
        self.transport = transport
        self.role = role

    def health(self) -> dict[str, Any]:
        return self.transport.call("health_check")

    def observe(self) -> dict[str, Any]:
        return self.transport.call("get_observation", role=self.role)

    def validate(self, action: dict[str, Any]) -> dict[str, Any]:
        return self.transport.call("validate_action", role=self.role, action=action)

    def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.transport.call("submit_turn", payload=payload)

    def send_message(self, message: str) -> dict[str, Any]:
        return self.transport.call("receive_message", from_role=self.role, message=message)

    def status(self) -> dict[str, Any]:
        return self.transport.call("get_match_status")

    def reset(self, cop: list[int], thief: list[int]) -> dict[str, Any]:
        return self.transport.call("reset", cop=cop, thief=thief)

    def messages(self) -> list[dict[str, str]]:
        """Delivered messages addressed to this server's inbox (bluff read-back)."""
        return self.transport.call("get_messages").get("messages", [])
