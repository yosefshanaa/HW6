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
prove the networked path end-to-end. The shared per-turn/scoring logic lives in
:mod:`cop_thief.match.remote_common`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from cop_thief.agents.agent_client import AgentClient
from cop_thief.constants import GameStatus
from cop_thief.domain.records import SubGameResult, TurnRecord
from cop_thief.domain.roles import PlayerRole
from cop_thief.match.match_orchestrator import MatchOutcome
from cop_thief.match.reconcile import diff_state
from cop_thief.match.remote_common import (
    NETWORK_ERRORS,
    build_strategies,
    result_for,
    role_groups,
    run_agent_turn,
    start_positions,
    totals_for,
)
from cop_thief.orchestrator.technical_loss import TechnicalLossError, run_clean
from cop_thief.shared.logging_setup import get_logger
from cop_thief.shared.replay import ReplayStore

_log = get_logger("remote_match")


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
        self.strategies = build_strategies(config)
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
            cop_group, thief_group = role_groups(self.group_1, self.group_2, self.half, index)
            attribution.append({"cop_group": cop_group, "thief_group": thief_group})
        totals = totals_for(results, self.group_1, self.group_2, self.half)
        return MatchOutcome(results, totals, flags, attribution)

    def _play_resilient(self, index: int) -> tuple[SubGameResult, list[str]]:
        """Play one sub-game; a mid-game network failure becomes a Technical Loss."""
        try:
            return self.play_sub_game(index)
        except NETWORK_ERRORS as exc:
            _log.warning("sub-game %d network failure (%s); voiding for rerun", index, exc)
            raise TechnicalLossError(str(exc)) from exc

    def play_sub_game(self, index: int) -> tuple[SubGameResult, list[str]]:
        """Reset both referees to the shared-seed start, then run the turn loop."""
        cop_pos, thief_pos = start_positions(self.grid_size, self.vision_radius, self.seed, index)
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
        return result_for(self.scoring, index, status), flags

    def _turn(self, index, role, memory, store, flags) -> tuple[bool, dict]:
        """Run the shared agent turn, then reconcile the two referees and log."""
        obs, action, message, res = run_agent_turn(
            self.strategies[role], role,
            auth=self.cop_client, mirror=self.thief_client, index=index, mem=memory[role],
        )
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
