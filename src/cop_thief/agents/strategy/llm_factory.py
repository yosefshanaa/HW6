"""Build an :class:`LlmStrategy` for a role from config (provider-agnostic).

Kept separate from ``heuristic.py`` so importing the heuristic never pulls in a
provider SDK; the concrete responder is selected here and the API key is read
from the environment inside the responder (guidelines §7.4).
"""

from __future__ import annotations

from collections.abc import Callable

from cop_thief.agents.llm_client import LlmClient
from cop_thief.agents.strategy.base import Strategy
from cop_thief.agents.strategy.llm_strategy import LlmStrategy
from cop_thief.domain.roles import PlayerRole
from cop_thief.shared.gatekeeper import ApiGatekeeper


def _responder_for(provider: str, model: str, config) -> Callable[..., str]:
    """Pick the concrete provider responder (only OpenAI is wired today)."""
    if provider == "openai":
        from cop_thief.agents.providers import openai_responder

        return openai_responder(
            model,
            temperature=float(config.get("llm.temperature", 0.7)),
            timeout=float(config.get("llm.per_turn_timeout_seconds", 30)),
        )
    raise ValueError(f"unsupported llm provider: {provider!r}")


def build_llm_strategy(role: PlayerRole, config, *, fallback: Strategy) -> LlmStrategy:
    """Wire a gatekeeper + provider responder + client into an LlmStrategy."""
    if config is None:
        raise ValueError("llm strategy requires a config")
    provider = config.get("llm.provider", "none")
    model = config.get("llm.model")
    gatekeeper = ApiGatekeeper.from_config(config, "llm")
    client = LlmClient(provider, model, gatekeeper, _responder_for(provider, model, config))
    return LlmStrategy(role, client, fallback=fallback)
