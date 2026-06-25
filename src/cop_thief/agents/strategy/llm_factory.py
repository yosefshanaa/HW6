"""Build an :class:`LlmStrategy` for a role from config (provider-agnostic).

Kept separate from ``heuristic.py`` so importing the heuristic never pulls in a
provider SDK; the concrete responder is selected here and the API key is read
from the environment inside the responder (guidelines §7.4).
"""

from __future__ import annotations

from collections.abc import Callable

from cop_thief.agents.llm_client import LlmClient
from cop_thief.agents.strategy.base import Strategy
from cop_thief.agents.strategy.llm_prompts import build_message_prompt, system_prompt
from cop_thief.agents.strategy.llm_strategy import LlmStrategy, _extract_json
from cop_thief.agents.strategy.search_strategy import SearchStrategy
from cop_thief.domain.action import Action
from cop_thief.domain.observation import Observation
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


def _build_client(config) -> LlmClient:
    """A gatekept LLM client wired to the configured provider responder."""
    provider = config.get("llm.provider", "none")
    model = config.get("llm.model")
    gatekeeper = ApiGatekeeper.from_config(config, "llm")
    return LlmClient(provider, model, gatekeeper, _responder_for(provider, model, config))


def build_llm_strategy(role: PlayerRole, config, *, fallback: Strategy) -> LlmStrategy:
    """Wire a gatekeeper + provider responder + client into an LlmStrategy."""
    if config is None:
        raise ValueError("llm strategy requires a config")
    return LlmStrategy(role, _build_client(config), fallback=fallback)


def _bluff_messenger(role: PlayerRole, config) -> Callable[..., str]:
    """A message-only LLM closure: asks the model for a bluff about the chosen move."""
    client = _build_client(config)
    system = system_prompt(role)

    def _say(obs: Observation, action: Action, memory: dict) -> str:
        raw = client.complete(build_message_prompt(role, obs, action, memory), system=system)
        data = _extract_json(raw) or {}
        return (str(data.get("say") or "")).strip()

    return _say


def build_search_strategy(
    role: PlayerRole, config, *, fallback: Strategy, with_llm_message: bool
) -> SearchStrategy:
    """Build the search-driven agent; ``with_llm_message`` adds the LLM bluff channel."""
    if config is None:
        raise ValueError("search strategy requires a config")
    messenger = _bluff_messenger(role, config) if with_llm_message else None
    return SearchStrategy(role, config=config, fallback=fallback, messenger=messenger)
