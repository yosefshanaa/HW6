"""Local inter-group match orchestration (PRD_bonus_match, shared spec §2.1).

``LocalMatch`` plays the fixed 6-sub-game bonus series between two
:class:`TeamSystem` peers on one machine. For each sub-game the cop side owns
the authoritative referee; the thief side runs a mirror engine and submits its
turns across the loopback MCP transport as the ``submit_turn`` envelope. After
every committed turn the two engines are reconciled and any divergence flagged.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from cop_thief.agents.agent_client import AgentClient, InProcessTransport
from cop_thief.constants import GameStatus
from cop_thief.domain.records import SubGameResult, TurnRecord
from cop_thief.domain.roles import PlayerRole
from cop_thief.engine.observation_service import fixed_start, random_start
from cop_thief.engine.referee import Referee
from cop_thief.engine.scoring import score_sub_game
from cop_thief.match.reconcile import diff_state
from cop_thief.match.team_system import TeamSystem
from cop_thief.mcp import tools
from cop_thief.orchestrator.technical_loss import TechnicalLossError, run_clean
from cop_thief.orchestrator.turn_loop import safe_fallback
from cop_thief.shared.replay import ReplayStore


@dataclass
class MatchOutcome:
    """A full local match: per-sub-game results, team totals, reconcile flags."""

    results: list[SubGameResult]
    totals_by_group: dict[str, int]
    flags: list[str] = field(default_factory=list)


class LocalMatch:
    """Plays the bonus series between two TeamSystems over the loopback path."""

    def __init__(
        self,
        config,
        team_a: TeamSystem,
        team_b: TeamSystem,
        *,
        results_dir=None,
        failure_injector=None,
    ) -> None:
        self.config = config
        self.team_a = team_a
        self.team_b = team_b
        self.num_games = int(config.get("num_games"))
        self.half = self.num_games // 2
        # The bonus match plays at the agreed radius (default 2), independent of
        # the local-series default which is lowered for balance (Task 2).
        self.vision_radius = int(config.get("match.vision_radius", config.get("vision_radius")))
        self.rng = random.Random(config.get("seed"))
        base = Path(results_dir or config.get("logging.results_dir", "results"))
        self.series_id = datetime.now(timezone.utc).strftime("match-%Y%m%dT%H%M%S")
        self.series_dir = base / self.series_id
        self._fail = failure_injector

    def roles(self, index: int) -> tuple[TeamSystem, TeamSystem]:
        """(cop_team, thief_team) for sub-game ``index`` per the fixed split."""
        if index <= self.half:
            return self.team_a, self.team_b
        return self.team_b, self.team_a

    def _start(self) -> tuple:
        if self.config.get("start_mode") == "fixed":
            return fixed_start(self.config.get("fixed_start"))
        return random_start(self.config.get("grid_size"), self.vision_radius, self.rng)

    def play_sub_game(self, index: int, attempt: int = 1):
        """Play one sub-game; raise TechnicalLossError if a glitch is injected."""
        cop_team, thief_team = self.roles(index)
        cop_pos, thief_pos = self._start()
        auth = cop_team.new_referee(self.vision_radius)
        auth.reset(cop_pos, thief_pos)
        mirror = thief_team.new_referee(self.vision_radius)
        mirror.reset(cop_pos, thief_pos)
        client = AgentClient(InProcessTransport(auth), PlayerRole.THIEF.value)
        store = ReplayStore(self.series_dir / f"sub_game_{index}.jsonl")
        teams = {PlayerRole.COP: cop_team, PlayerRole.THIEF: thief_team}
        cop_team.start_role(PlayerRole.COP, auth.max_barriers)
        thief_team.start_role(PlayerRole.THIEF, auth.max_barriers)
        flags: list[str] = []
        while auth.state.status is GameStatus.ONGOING:
            for role in (PlayerRole.THIEF, PlayerRole.COP):
                if self._fail and self._fail(index, attempt):
                    raise TechnicalLossError(f"injected failure sub-game {index}")
                if self._turn(index, role, teams, auth, mirror, client, store, flags):
                    break
            else:
                continue
            break
        result = self._result(index, auth)
        return result, teams[result.winner].name, flags

    def _turn(self, index, role, teams, auth, mirror, client, store, flags) -> bool:
        team, opp = teams[role], teams[role.opponent]
        obs = auth.observe(role)
        mem = team.memory[role]
        if obs.visible_opponent is not None:
            mem["last_known_opponent"] = obs.visible_opponent
        strat = team.strategy_for(role)
        action = strat.decide(obs, mem)
        message = strat.compose_message(obs, action, mem)
        valid, reason = auth.validate(role, action)
        if not valid:
            action, reason = safe_fallback(auth, role, action, reason)
        envelope = {"sub_game": index, "move_number": obs.move_number,
                    "role": role.value, "message": message, "action": action.as_dict()}
        result = client.submit(envelope)              # authoritative MCP submit_turn
        tools.submit_turn(mirror, envelope)           # independent mirror engine
        mismatch = diff_state(auth.state.snapshot(), mirror.state.snapshot())
        flags.extend(f"sub_game {index} move {obs.move_number}: {d}" for d in mismatch)
        client.send_message(message)
        opp.memory[role.opponent].setdefault("received_messages", []).append(message)
        store.append(TurnRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            sub_game=index, move_number=obs.move_number, role=role,
            message=message, action=action.as_dict(), observation=obs.as_dict(),
            validation={"accepted": result["accepted"], "reason": result["reason"] or reason,
                        "capture": result["capture"], "mismatch": mismatch},
            resulting_state=auth.state.snapshot(),
        ))
        return result["terminal"]

    def _result(self, index: int, auth: Referee) -> SubGameResult:
        state = auth.state
        winner = PlayerRole.COP if state.status is GameStatus.COP_WIN else PlayerRole.THIEF
        cop_score, thief_score = score_sub_game(auth.scoring, winner)
        return SubGameResult(index, winner, state.thief_moves, cop_score, thief_score)

    def play_series(self) -> MatchOutcome:
        """Play ``num_games`` clean sub-games, re-running technical losses."""
        results: list[SubGameResult] = []
        flags: list[str] = []
        for index in range(1, self.num_games + 1):
            (result, _winner, sg_flags), _voided = run_clean(
                lambda attempt, i=index: self.play_sub_game(i, attempt)
            )
            results.append(result)
            flags.extend(sg_flags)
        return MatchOutcome(results, self._totals(results), flags)

    def _totals(self, results: list[SubGameResult]) -> dict[str, int]:
        totals = {self.team_a.name: 0, self.team_b.name: 0}
        for r in results:
            cop_team, thief_team = self.roles(r.index)
            totals[cop_team.name] += r.cop_score
            totals[thief_team.name] += r.thief_score
        return totals
