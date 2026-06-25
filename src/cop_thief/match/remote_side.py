"""Play-our-half driver: run OUR agent in a real two-team match over MCP/HTTP.

Unlike :class:`RemoteMatch` (one orchestrator driving *both* agents — our us-vs-us
proof), ``RemoteSide`` drives **only our role** each sub-game; the opponent drives
theirs. Both teams run an instance against the same two referees (the Cop-side
server is authoritative, the Thief-side server is the in-sync mirror) and submit
every move to **both**.

Coordination is turn-based and race-safe: a side acts only when **both** referees
agree it is its turn (so the other side, mid dual-submit, can never wedge a move in
out of order). Sub-game boundaries are disambiguated by the per-(seed,index) start
positions — both teams derive the same ones — so no extra handshake is needed.
Reset is hardened for cross-team play and survives either reset convention on the
peer's side: the **Cop host resets both referees** (the peer may not reset a mirror
it doesn't own), and the **Thief also resets its own mirror** as a safety net (the
peer's Cop may reset only its own server). All resets target the same agreed start,
so the overlap is idempotent. Shared turn/scoring logic lives in
:mod:`cop_thief.match.remote_common`.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from cop_thief.agents.agent_client import AgentClient
from cop_thief.constants import GameStatus
from cop_thief.domain.records import SubGameResult, TurnRecord
from cop_thief.domain.roles import PlayerRole
from cop_thief.match.match_orchestrator import MatchOutcome
from cop_thief.match.remote_common import (
    build_strategies,
    result_for,
    role_groups,
    run_agent_turn,
    start_positions,
    totals_for,
)
from cop_thief.shared.logging_setup import get_logger
from cop_thief.shared.replay import ReplayStore

_log = get_logger("remote_side")

# (authoritative Cop-referee client, mirror Thief-referee client) for a sub-game.
ClientsFor = Callable[[int], tuple[AgentClient, AgentClient]]


class RemoteSide:
    """Drives our agent for its role each sub-game against two remote referees."""

    POLL = 0.25                 # seconds between turn polls
    RESET_GRACE = 1.5           # host waits this long before resetting the next sub-game
    SUBGAME_TIMEOUT = 120.0     # abort if the opponent stalls this long

    def __init__(
        self,
        config,
        my_group: str,
        clients_for: ClientsFor,
        *,
        group_1: str,
        group_2: str,
        results_dir: str | Path | None = None,
    ) -> None:
        self.config = config
        self.my_group = my_group
        self.clients_for = clients_for
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
        self.series_dir = base / datetime.now(timezone.utc).strftime(
            f"side-{my_group}-%Y%m%dT%H%M%S"
        )
        self.results: list[SubGameResult] = []

    def my_role(self, index: int) -> PlayerRole:
        """Our role in sub-game ``index`` (Cop first half for group_1, then swap)."""
        cop_group = self.group_1 if index <= self.half else self.group_2
        return PlayerRole.COP if self.my_group == cop_group else PlayerRole.THIEF

    def play_series(self) -> list[SubGameResult]:
        """Play our half of all sub-games; return our per-sub-game results."""
        for index in range(1, self.num_games + 1):
            self.results.append(self.play_sub_game(index))
        return self.results

    def outcome(self) -> MatchOutcome:
        """Bundle our results into a MatchOutcome (totals + attribution) for the report."""
        attribution = [
            dict(zip(("cop_group", "thief_group"),
                     role_groups(self.group_1, self.group_2, self.half, r.index), strict=True))
            for r in self.results
        ]
        totals = totals_for(self.results, self.group_1, self.group_2, self.half)
        return MatchOutcome(self.results, totals, [], attribution)

    def play_sub_game(self, index: int) -> SubGameResult:
        role = self.my_role(index)
        auth, mirror = self.clients_for(index)
        cop_pos, thief_pos = start_positions(self.grid_size, self.vision_radius, self.seed, index)
        # Reset hardened for cross-team play. As Cop host we reset BOTH referees (the
        # peer may not reset a mirror it doesn't own — without this its stale mirror
        # stays terminal and wedges the sub-game). As Thief we ALSO reset our own
        # mirror (the peer's Cop may reset only its own server). All resets target the
        # same agreed start, so the overlap is idempotent.
        if role is PlayerRole.COP:                       # Cop host: reset both referees
            time.sleep(self.RESET_GRACE)                 # let the peer finish the prior sub-game
            mirror.reset(cop_pos.as_list(), thief_pos.as_list())   # mirror first...
            auth.reset(cop_pos.as_list(), thief_pos.as_list())     # ...then auth (the Thief waits on it)
            _log.info("sub-game %d: reset both referees as cop host", index)
        else:                                            # Thief: confirm cop start, reset own mirror
            self._await_cop_start(index, auth, cop_pos, thief_pos)
            mirror.reset(cop_pos.as_list(), thief_pos.as_list())
            _log.info("sub-game %d: cop start confirmed; reset our thief mirror", index)
        mem = {"max_barriers": self.max_barriers} if role is PlayerRole.COP else {}
        store = ReplayStore(self.series_dir / f"sub_game_{index}.jsonl")
        deadline = time.time() + self.SUBGAME_TIMEOUT
        while True:
            cs, ms = auth.status(), mirror.status()
            if cs["status"] != GameStatus.ONGOING.value:
                break
            if cs["turn"] == role.value and ms["turn"] == role.value:
                self._play_turn(index, role, auth, mirror, mem, store)
                deadline = time.time() + self.SUBGAME_TIMEOUT
            elif time.time() > deadline:
                raise TimeoutError(f"sub-game {index}: opponent stalled past {self.SUBGAME_TIMEOUT}s")
            else:
                time.sleep(self.POLL)
        return result_for(self.scoring, index, auth.status())

    def _await_cop_start(self, index, auth, cop_pos, thief_pos) -> None:
        """Wait until the Cop-side authoritative server shows the agreed fresh start.

        The Cop side owns its server's reset; we (Thief) confirm it is at the
        seeded start for ``index`` before mirroring that start onto our own server.
        """
        want = (cop_pos.as_list(), thief_pos.as_list())
        deadline = time.time() + self.SUBGAME_TIMEOUT
        while time.time() <= deadline:
            cs = auth.status()
            fresh = (
                cs["status"] == GameStatus.ONGOING.value and cs["thief_moves"] == 0
                and (cs["cop"], cs["thief"]) == want
            )
            if fresh:
                return
            time.sleep(self.POLL)
        raise TimeoutError(f"sub-game {index}: cop host never reset to the expected start")

    def _play_turn(self, index, role, auth, mirror, mem, store) -> None:
        """Run the shared agent turn against our two referees, then log it."""
        obs, action, message, res = run_agent_turn(
            self.strategies[role], role, auth=auth, mirror=mirror, index=index, mem=mem,
        )
        store.append(TurnRecord(
            timestamp=datetime.now(timezone.utc).isoformat(), sub_game=index,
            move_number=obs.move_number, role=role, message=message,
            action=action.as_dict(), observation=obs.as_dict(),
            validation={"accepted": res["accepted"], "reason": res["reason"],
                        "capture": res["capture"]},
            resulting_state=auth.status(),
        ))
