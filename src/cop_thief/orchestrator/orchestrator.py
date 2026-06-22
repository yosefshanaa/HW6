"""Series + sub-game orchestration (PLAN §10, PRD §6.6)."""

from __future__ import annotations

import random
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from cop_thief.agents.strategy.heuristic import make_strategy
from cop_thief.constants import GameStatus
from cop_thief.domain.records import SubGameResult
from cop_thief.domain.roles import PlayerRole
from cop_thief.engine.observation_service import fixed_start, random_start
from cop_thief.engine.referee import Referee
from cop_thief.engine.scoring import score_sub_game
from cop_thief.orchestrator.technical_loss import TechnicalLossError, run_clean
from cop_thief.orchestrator.turn_loop import play_turn
from cop_thief.shared.replay import ReplayStore


class Orchestrator:
    """Plays a full clean series of sub-games with baseline (or LLM) agents."""

    def __init__(
        self,
        config,
        *,
        results_dir: str | Path | None = None,
        failure_injector: Callable[[int, int], bool] | None = None,
    ) -> None:
        self.config = config
        self.referee = Referee.from_config(config)
        self.cop = make_strategy(PlayerRole.COP, config.get("agents.cop_strategy", "heuristic"))
        self.thief = make_strategy(PlayerRole.THIEF, config.get("agents.thief_strategy", "heuristic"))
        self.rng = random.Random(config.get("seed"))
        base = Path(results_dir or config.get("logging.results_dir", "results"))
        self.series_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        self.series_dir = base / self.series_id
        self._fail = failure_injector

    def _start_positions(self):
        if self.config.get("start_mode") == "fixed":
            return fixed_start(self.config.get("fixed_start"))
        return random_start(
            self.referee.grid_size,
            self.referee.vision_radius,
            self.rng,
            max_distance=self.config.get("start_distance_max"),
        )

    def play_sub_game(self, index: int, attempt: int = 1) -> SubGameResult:
        """Play one sub-game; raise TechnicalLossError if a glitch is injected."""
        cop_pos, thief_pos = self._start_positions()
        self.referee.reset(cop_pos, thief_pos)
        store = ReplayStore(self.series_dir / f"sub_game_{index}.jsonl")
        memory = {
            PlayerRole.COP: {"max_barriers": self.referee.max_barriers},
            PlayerRole.THIEF: {},
        }
        order = (
            (PlayerRole.THIEF, self.thief),
            (PlayerRole.COP, self.cop),
        )
        while self.referee.state.status is GameStatus.ONGOING:
            for role, strat in order:
                if self._fail and self._fail(index, attempt):
                    raise TechnicalLossError(f"injected failure sub-game {index}")
                result = play_turn(
                    self.referee, role, strat, memory[role], memory[role.opponent], index, store
                )
                if result.terminal:
                    break
            else:
                continue
            break
        return self._result(index)

    def _result(self, index: int) -> SubGameResult:
        state = self.referee.state
        winner = PlayerRole.COP if state.status is GameStatus.COP_WIN else PlayerRole.THIEF
        cop_score, thief_score = score_sub_game(self.referee.scoring, winner)
        return SubGameResult(index, winner, state.thief_moves, cop_score, thief_score)

    def play_series(self) -> list[SubGameResult]:
        """Play ``num_games`` clean sub-games, re-running technical losses."""
        results: list[SubGameResult] = []
        for index in range(1, int(self.config.get("num_games")) + 1):
            result, _voided = run_clean(lambda attempt, i=index: self.play_sub_game(i, attempt))
            results.append(result)
        return results
