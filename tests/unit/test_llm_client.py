"""LLM client seam tests (PLAN §11)."""

from __future__ import annotations

import pytest

from cop_thief.agents.llm_client import LlmClient
from cop_thief.shared.gatekeeper import ApiGatekeeper


def make_gatekeeper():
    return ApiGatekeeper({"requests_per_minute": 60}, sleep=lambda _s: None, clock=lambda: 0.0)


def test_complete_uses_injected_responder():
    client = LlmClient("none", "test", make_gatekeeper(), responder=lambda p: f"echo:{p}")
    assert client.complete("hi") == "echo:hi"


def test_complete_without_responder_raises():
    client = LlmClient("none", "test", make_gatekeeper())
    with pytest.raises(NotImplementedError):
        client.complete("hi")
