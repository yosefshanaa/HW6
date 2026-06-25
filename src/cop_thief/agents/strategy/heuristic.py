"""Baseline heuristic strategies + the strategy factory (PRD_agent_strategy §2.2).

The Cop and Thief bodies live in :mod:`heuristic_cop` / :mod:`heuristic_thief`
(shared belief helpers in :mod:`heuristic_common`); this module re-exports them
and the ``make_strategy`` factory, keeping the historical public import surface
(`from cop_thief.agents.strategy.heuristic import make_strategy`).
"""

from __future__ import annotations

from cop_thief.agents.strategy.base import Strategy
from cop_thief.agents.strategy.heuristic_common import _message_hint
from cop_thief.agents.strategy.heuristic_cop import HeuristicCop
from cop_thief.agents.strategy.heuristic_thief import HeuristicThief
from cop_thief.domain.roles import PlayerRole

__all__ = ["HeuristicCop", "HeuristicThief", "make_strategy", "_message_hint"]


def make_strategy(role: PlayerRole, name: str = "heuristic", *, config=None) -> Strategy:
    """Factory for a strategy by role and name.

    ``heuristic`` (default) needs no config; ``llm`` builds the hybrid LLM
    strategy (LLM move + heuristic legal-guard); ``search`` drives the move with a
    bounded minimax over the real rules (heuristic under fog) and a heuristic
    bluff; ``search_llm`` is ``search`` with the bluff written by the LLM. All but
    ``heuristic`` need ``config``; the heuristic is always the fog/legal fallback.
    """
    base = HeuristicCop() if role is PlayerRole.COP else HeuristicThief()
    if name == "heuristic":
        return base
    if name == "llm":
        from cop_thief.agents.strategy.llm_factory import build_llm_strategy

        return build_llm_strategy(role, config, fallback=base)
    if name in ("search", "search_llm"):
        from cop_thief.agents.strategy.llm_factory import build_search_strategy

        return build_search_strategy(
            role, config, fallback=base, with_llm_message=(name == "search_llm")
        )
    raise ValueError(f"unknown strategy: {name}")
