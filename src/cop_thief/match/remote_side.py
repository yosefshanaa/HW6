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
**Each team resets only the server it owns** (inter-team agreement): the Cop-side
resets the authoritative server to the agreed start (after a short grace so the peer
has finished the previous sub-game); the Thief-side confirms that start, then mirrors
it onto its own server. Neither team resets the other's server.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
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
        self.strategies = {
            PlayerRole.COP: make_strategy(
                PlayerRole.COP, config.get("agents.cop_strategy", "heuristic"), config=config
            ),
            PlayerRole.THIEF: make_strategy(
                PlayerRole.THIEF, config.get("agents.thief_strategy", "heuristic"), config=config
            ),
        }
        base = Path(results_dir or config.get("logging.results_dir", "results"))
        self.series_dir = base / datetime.now(timezone.utc).strftime(
            f"side-{my_group}-%Y%m%dT%H%M%S"
        )
        self.results: list[SubGameResult] = []

    def my_role(self, index: int) -> PlayerRole:
        """Our role in sub-game ``index`` (Cop first half for group_1, then swap)."""
        cop_group = self.group_1 if index <= self.half else self.group_2
        return PlayerRole.COP if self.my_group == cop_group else PlayerRole.THIEF

    def _start_positions(self, index: int):
        rng = random.Random(f"{self.seed}:{index}")
        return random_start(self.grid_size, self.vision_radius, rng)

    def play_series(self) -> list[SubGameResult]:
        """Play our half of all sub-games; return our per-sub-game results."""
        for index in range(1, self.num_games + 1):
            self.results.append(self.play_sub_game(index))
        return self.results

    def _groups(self, index: int) -> tuple[str, str]:
        """(cop_group, thief_group) for ``index`` per the fixed role split."""
        if index <= self.half:
            return self.group_1, self.group_2
        return self.group_2, self.group_1

    def outcome(self) -> MatchOutcome:
        """Bundle our results into a MatchOutcome (totals + attribution) for the report."""
        totals = {self.group_1: 0, self.group_2: 0}
        attribution: list[dict[str, str]] = []
        for r in self.results:
            cop_group, thief_group = self._groups(r.index)
            attribution.append({"cop_group": cop_group, "thief_group": thief_group})
            totals[cop_group] += r.cop_score
            totals[thief_group] += r.thief_score
        return MatchOutcome(self.results, totals, [], attribution)

    def play_sub_game(self, index: int) -> SubGameResult:
        role = self.my_role(index)
        auth, mirror = self.clients_for(index)
        our_view = auth if role is PlayerRole.COP else mirror
        cop_pos, thief_pos = self._start_positions(index)
        # Each team resets ONLY the server it owns (inter-team agreement). The Cop side
        # resets the authoritative server; the Thief side confirms that start, then
        # mirrors it onto its own server — so a stale mirror can't wedge the next
        # sub-game (the bug that stalled the cross-team run at the role swap).
        if role is PlayerRole.COP:                       # we own the authoritative (cop) server
            time.sleep(self.RESET_GRACE)                 # let the peer finish the prior sub-game
            auth.reset(cop_pos.as_list(), thief_pos.as_list())
            _log.info("sub-game %d: reset our cop server as host", index)
        else:                                            # we own the mirror (thief) server
            self._await_cop_start(index, auth, cop_pos, thief_pos)
            mirror.reset(cop_pos.as_list(), thief_pos.as_list())
            _log.info("sub-game %d: cop start confirmed; mirrored onto our thief server", index)
        mem = {"max_barriers": self.max_barriers} if role is PlayerRole.COP else {}
        store = ReplayStore(self.series_dir / f"sub_game_{index}.jsonl")
        deadline = time.time() + self.SUBGAME_TIMEOUT
        while True:
            cs, ms = auth.status(), mirror.status()
            if cs["status"] != GameStatus.ONGOING.value:
                break
            if cs["turn"] == role.value and ms["turn"] == role.value:
                self._play_turn(index, role, auth, mirror, our_view, mem, store)
                deadline = time.time() + self.SUBGAME_TIMEOUT
            elif time.time() > deadline:
                raise TimeoutError(f"sub-game {index}: opponent stalled past {self.SUBGAME_TIMEOUT}s")
            else:
                time.sleep(self.POLL)
        return self._result(index, auth.status())

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

    def _play_turn(self, index, role, auth, mirror, our_view, mem, store) -> None:
        # Read the opponent's bluff over MCP from our own view server before deciding.
        inbox = our_view.messages()
        mem["received_messages"] = [
            m["message"] for m in inbox if m.get("from") == role.opponent.value
        ]
        obs = Observation.from_dict(our_view.observe())
        if obs.visible_opponent is not None:
            mem["last_known_opponent"] = obs.visible_opponent
        action = self._guard_legal(self.strategies[role].decide(obs, mem), obs)
        message = self.strategies[role].compose_message(obs, action, mem)
        envelope = {
            "sub_game": index, "move_number": obs.move_number, "role": role.value,
            "message": message, "action": action.as_dict(),
        }
        res = auth.submit(envelope)        # authoritative
        mirror.submit(envelope)            # mirror (kept in sync)
        # Deliver our (possibly false) message to the opponent's view server.
        opp_view = mirror if role is PlayerRole.COP else auth
        opp_view.transport.call("receive_message", from_role=role.value, message=message)
        store.append(TurnRecord(
            timestamp=datetime.now(timezone.utc).isoformat(), sub_game=index,
            move_number=obs.move_number, role=role, message=message,
            action=action.as_dict(), observation=obs.as_dict(),
            validation={"accepted": res["accepted"], "reason": res["reason"],
                        "capture": res["capture"]},
            resulting_state=auth.status(),
        ))

    def _guard_legal(self, action: Action, obs: Observation) -> Action:
        if action.type is ActionType.BARRIER:
            return action
        cells = legal_neighbor_cells(obs)
        return action if (action.to in cells or not cells) else Action.move(cells[0])

    def _result(self, index: int, status: dict) -> SubGameResult:
        winner = (
            PlayerRole.COP if status["status"] == GameStatus.COP_WIN.value else PlayerRole.THIEF
        )
        cop_score, thief_score = score_sub_game(self.scoring, winner)
        return SubGameResult(index, winner, status["thief_moves"], cop_score, thief_score)
