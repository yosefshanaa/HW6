"""MCP client wrapper + in-process transport (PLAN §8, PRD_mcp_servers §2.3).

``AgentClient`` talks to one server's tools through a ``Transport``. The
``InProcessTransport`` binds directly to a referee + inbox so the client/server
tool path can run (and be contract-tested) without a network.
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
        raise ValueError(f"unknown tool: {tool}")


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
