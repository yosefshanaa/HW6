"""Networked inter-team match driver over MCP/HTTP (PRD_bonus_match, shared spec §2).

Unlike :class:`LocalMatch` (both teams simulated in one process over the loopback
transport), ``RemoteMatch`` plays the 6-sub-game series against **two live MCP
servers** through :class:`AgentClient`s — the real cross-team path. The Cop server
holds the authoritative referee and serves the Cop's fog-of-war view; the Thief
server is the in-sync mirror and serves the Thief's view (each server is role-bound,
so a view can never leak the opponent's hidden state). Every move is submitted to
**both** referees and their statuses reconciled after each turn (mirror-and-flag).

For the real match you point ``cop_client`` at whoever owns the authoritative
referee for the sub-game and ``thief_client`` at the mirror; the loop is identical.
Here both clients can point at our own deployed servers (us driving both roles) to
prove the networked path end-to-end.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from pathlib import Path

from cop_thief.agents.agent_client import AgentClient
from cop_thief.agents.strategy.base import legal_neighbor_cells
from cop_thief.agents.strategy.heuristic import make_strategy
from cop_thief.constants import ActionType, GameStatus
from cop_thief.domain.action import Action
from cop_thief.domain.observation import Observation
from cop_thief.domain.records import SubGameResult, TurnRecord
from cop_thief.domain.roles import PlayerRole
from cop_thief.engine.observation_service import random_start
from cop_thief.engine.scoring import score_sub_game
from cop_thief.match.match_orchestrator import MatchOutcome
from cop_thief.match.reconcile import diff_state
from cop_thief.orchestrator.technical_loss import TechnicalLossError, run_clean
from cop_thief.shared.logging_setup import get_logger
from cop_thief.shared.replay import ReplayStore

_log = get_logger("remote_match")

# A failure of one of these mid-sub-game is a Technical Loss (void + rerun), not a crash.
_NETWORK_ERRORS: tuple[type[BaseException], ...] = (ConnectionError, TimeoutError, OSError)
try:  # httpx ships with the mcp extra; widen the net when present
    import httpx

    _NETWORK_ERRORS = (*_NETWORK_ERRORS, httpx.HTTPError)
except ImportError:  # pragma: no cover
    pass


class RemoteMatch:
    """Plays the bonus series across two remote MCP referees (HTTP transport)."""

    def __init__(
        self,
        config,
        cop_client: AgentClient,
        thief_client: AgentClient,
        *,
        results_dir: str | Path | None = None,
        group_1: str = "group_1",
        group_2: str = "group_2",
    ) -> None:
        self.config = config
        self.cop_client = cop_client          # authoritative referee + Cop view
        self.thief_client = thief_client      # mirror referee + Thief view
        self.num_games = int(config.get("num_games"))
        self.half = self.num_games // 2
        self.vision_radius = int(config.get("match.vision_radius", config.get("vision_radius")))
        self.max_barriers = int(config.get("max_barriers"))
        self.scoring = config.get("scoring")
        self.grid_size = config.get("grid_size")
        self.seed = config.get("seed")
        self.group_1, self.group_2 = group_1, group_2
        self.strategies = {
            PlayerRole.COP: make_strategy(
                PlayerRole.COP, config.get("agents.cop_strategy", "heuristic"), config=config
            ),
            PlayerRole.THIEF: make_strategy(
                PlayerRole.THIEF, config.get("agents.thief_strategy", "heuristic"), config=config
            ),
        }
        base = Path(results_dir or config.get("logging.results_dir", "results"))
        self.series_id = datetime.now(timezone.utc).strftime("remote-%Y%m%dT%H%M%S")
        self.series_dir = base / self.series_id

    def play_series(self) -> MatchOutcome:
        """Play all sub-games; return per-sub-game results, totals, reconcile flags."""
        results: list[SubGameResult] = []
        flags: list[str] = []
        attribution: list[dict[str, str]] = []
        for index in range(1, self.num_games + 1):
            (result, sg_flags), voided = run_clean(lambda _a, i=index: self._play_resilient(i))
            if voided:
                flags.append(f"sub_game {index}: {voided} technical-loss rerun(s)")
            results.append(result)
            flags.extend(sg_flags)
            cop_group, thief_group = self._groups(index)
            attribution.append({"cop_group": cop_group, "thief_group": thief_group})
        return MatchOutcome(results, self._totals(results), flags, attribution)

    def _play_resilient(self, index: int) -> tuple[SubGameResult, list[str]]:
        """Play one sub-game; a mid-game network failure becomes a Technical Loss."""
        try:
            return self.play_sub_game(index)
        except _NETWORK_ERRORS as exc:
            _log.warning("sub-game %d network failure (%s); voiding for rerun", index, exc)
            raise TechnicalLossError(str(exc)) from exc

    def _start_positions(self, index: int):
        """Start cells derived deterministically from (seed, index).

        Per-index (not a running RNG) so a rerun — or the partner team computing the
        same seed — always yields the identical start for that sub-game.
        """
        rng = random.Random(f"{self.seed}:{index}")
        return random_start(self.grid_size, self.vision_radius, rng)

    def play_sub_game(self, index: int) -> tuple[SubGameResult, list[str]]:
        """Reset both referees to the shared-seed start, then run the turn loop."""
        cop_pos, thief_pos = self._start_positions(index)
        self.cop_client.reset(cop_pos.as_list(), thief_pos.as_list())
        self.thief_client.reset(cop_pos.as_list(), thief_pos.as_list())
        memory = {PlayerRole.COP: {"max_barriers": self.max_barriers}, PlayerRole.THIEF: {}}
        store = ReplayStore(self.series_dir / f"sub_game_{index}.jsonl")
        flags: list[str] = []
        status = self.cop_client.status()
        while status["status"] == GameStatus.ONGOING.value:
            terminal = False
            for role in (PlayerRole.THIEF, PlayerRole.COP):
                terminal, status = self._turn(index, role, memory, store, flags)
                if terminal:
                    break
            if terminal:
                break
        return self._result(index, status), flags

    def _turn(self, index, role, memory, store, flags) -> tuple[bool, dict]:
        """Read bluffs → observe → decide → submit to BOTH referees → reconcile."""
        client = self.cop_client if role is PlayerRole.COP else self.thief_client
        opp_client = self.thief_client if role is PlayerRole.COP else self.cop_client
        mem = memory[role]
        # Bluff channel (over MCP): read the opponent's delivered messages from our
        # own server's inbox before deciding, so the agent's prompt sees them.
        inbox = client.messages()
        mem["received_messages"] = [
            m["message"] for m in inbox if m.get("from") == role.opponent.value
        ]
        obs = Observation.from_dict(client.observe())
        if obs.visible_opponent is not None:
            mem["last_known_opponent"] = obs.visible_opponent
        strat = self.strategies[role]
        action = self._guard_legal(strat.decide(obs, mem), obs)
        message = strat.compose_message(obs, action, mem)
        envelope = {
            "sub_game": index, "move_number": obs.move_number, "role": role.value,
            "message": message, "action": action.as_dict(),
        }
        res = self.cop_client.submit(envelope)        # authoritative commit
        self.thief_client.submit(envelope)            # mirror commit (kept in sync)
        # Deliver our (possibly false) message to the opponent's server inbox.
        opp_client.transport.call("receive_message", from_role=role.value, message=message)
        auth_status, mirror_status = self.cop_client.status(), self.thief_client.status()
        mismatch = diff_state(auth_status, mirror_status)
        flags.extend(f"sub_game {index} move {obs.move_number}: {d}" for d in mismatch)
        store.append(TurnRecord(
            timestamp=datetime.now(timezone.utc).isoformat(), sub_game=index,
            move_number=obs.move_number, role=role, message=message,
            action=action.as_dict(), observation=obs.as_dict(),
            validation={"accepted": res["accepted"], "reason": res["reason"],
                        "capture": res["capture"], "mismatch": mismatch},
            resulting_state=auth_status,
        ))
        return res["terminal"], auth_status

    def _guard_legal(self, action: Action, obs: Observation) -> Action:
        """Last-ditch legality guard so a turn can never forfeit on an illegal move."""
        if action.type is ActionType.BARRIER:
            return action
        cells = legal_neighbor_cells(obs)
        if action.to in cells or not cells:
            return action
        return Action.move(cells[0])

    def _groups(self, index: int) -> tuple[str, str]:
        """(cop_group, thief_group) for ``index`` per the fixed role split."""
        if index <= self.half:
            return self.group_1, self.group_2
        return self.group_2, self.group_1

    def _result(self, index: int, status: dict) -> SubGameResult:
        winner = (
            PlayerRole.COP if status["status"] == GameStatus.COP_WIN.value else PlayerRole.THIEF
        )
        cop_score, thief_score = score_sub_game(self.scoring, winner)
        return SubGameResult(index, winner, status["thief_moves"], cop_score, thief_score)

    def _totals(self, results: list[SubGameResult]) -> dict[str, int]:
        totals = {self.group_1: 0, self.group_2: 0}
        for r in results:
            cop_group, thief_group = self._groups(r.index)
            totals[cop_group] += r.cop_score
            totals[thief_group] += r.thief_score
        return totals
