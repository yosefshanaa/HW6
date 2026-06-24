"""MCP client wrapper + transports (PLAN §8, PRD_mcp_servers §2.3).

``AgentClient`` talks to one server's tools through a ``Transport``. Two transports
are provided: ``InProcessTransport`` binds directly to a referee + inbox (so the
client/server tool path is contract-testable without a network), and
``HttpTransport`` reaches a *remote* MCP server over HTTP with bearer auth — the
path used for the cross-team bonus match. Both honour the same interface, so the
match machinery is transport-agnostic.
"""

from __future__ import annotations

import contextlib
import time
from abc import ABC, abstractmethod
from typing import Any

from cop_thief.engine.referee import Referee
from cop_thief.mcp import tools
from cop_thief.shared.logging_setup import get_logger

_log = get_logger("agent_client")

# Connection-level failures worth a reconnect+retry (a stale session, a dropped
# keepalive stream, or a Cloud Run cold start). NOT HTTP 4xx/5xx — those surface.
_RETRYABLE: tuple[type[BaseException], ...] = (ConnectionError, TimeoutError, OSError)
try:  # httpx ships with the mcp extra
    import httpx

    _RETRYABLE = (*_RETRYABLE, httpx.TransportError)  # Connect/Read/Pool timeouts, protocol errors
except ImportError:  # pragma: no cover
    pass
try:
    import anyio

    _RETRYABLE = (*_RETRYABLE, anyio.BrokenResourceError)
except ImportError:  # pragma: no cover
    pass


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
    in-memory tests (no socket). Resilient by design: a dropped session, stale
    keepalive, or Cloud Run cold start triggers a reconnect + retry with backoff
    instead of crashing (the referee state is server-side global, so a new session
    sees the same game). ``fastmcp`` is imported lazily (the optional ``mcp`` extra).
    """

    _RETRIES = 4          # reconnect+retry attempts on a connection-level failure
    _BACKOFF = 2.5        # seconds between attempts (long enough to ride a cold start)

    def __init__(self, target: Any, *, token: str | None = None, timeout: float = 60.0) -> None:
        import asyncio

        self._loop = asyncio.new_event_loop()
        if isinstance(target, str):
            # Strip a trailing slash: FastMCP serves at ``/mcp`` and ``/mcp/``
            # 307-redirects, on which httpx drops the auth header → a spurious 401.
            target = target.rstrip("/")
        self._target = target
        self._token = token
        self._timeout = timeout
        self._client: Any = None
        self._open()

    def _build_client(self) -> Any:
        from fastmcp import Client

        if isinstance(self._target, str) and self._token:
            from fastmcp.client.auth import BearerAuth

            return Client(self._target, auth=BearerAuth(self._token), timeout=self._timeout)
        return Client(self._target, timeout=self._timeout)

    def _open(self) -> None:
        self._client = self._build_client()
        self._loop.run_until_complete(self._client.__aenter__())

    def _reconnect(self) -> None:
        with contextlib.suppress(Exception):  # the old session is already broken
            self._loop.run_until_complete(self._client.__aexit__(None, None, None))
        self._open()

    def call(self, tool: str, **kwargs: Any) -> dict[str, Any]:
        keys = _HTTP_TOOL_ARGS.get(tool)
        if keys is None:
            raise ValueError(f"unknown tool: {tool}")
        args = {k: kwargs[k] for k in keys}
        last: BaseException | None = None
        for attempt in range(self._RETRIES):
            try:
                return self._loop.run_until_complete(self._client.call_tool(tool, args)).data
            except _RETRYABLE as exc:
                last = exc
                _log.warning("MCP %s failed (%s); reconnect+retry %d/%d",
                             tool, type(exc).__name__, attempt + 1, self._RETRIES)
                if attempt < self._RETRIES - 1:
                    time.sleep(self._BACKOFF)
                    try:
                        self._reconnect()
                    except Exception as rexc:  # noqa: BLE001 - keep the original error if reconnect fails
                        last = rexc
        raise last  # type: ignore[misc]

    def close(self) -> None:
        """Close the client session and its event loop (call after the match)."""
        try:
            with contextlib.suppress(Exception):
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
