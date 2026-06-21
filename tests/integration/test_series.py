"""End-to-end series orchestration tests (PRD §6.6, acceptance criteria)."""

from __future__ import annotations

from cop_thief.constants import GameStatus
from cop_thief.domain.roles import PlayerRole
from cop_thief.orchestrator.orchestrator import Orchestrator


def test_full_series_runs_and_scores(config, tmp_path):
    orch = Orchestrator(config, results_dir=tmp_path)
    results = orch.play_series()
    assert len(results) == config.get("num_games")
    for r in results:
        assert r.winner in (PlayerRole.COP, PlayerRole.THIEF)
        assert r.moves_played <= config.get("max_moves")
        if r.winner is PlayerRole.COP:
            assert (r.cop_score, r.thief_score) == (20, 5)
        else:
            assert (r.cop_score, r.thief_score) == (5, 10)


def test_series_writes_replay_logs(config, tmp_path):
    orch = Orchestrator(config, results_dir=tmp_path)
    orch.play_series()
    logs = list(tmp_path.glob("*/sub_game_*.jsonl"))
    assert len(logs) == config.get("num_games")
    assert logs[0].read_text(encoding="utf-8").strip() != ""


def test_single_sub_game_terminates(config, tmp_path):
    orch = Orchestrator(config, results_dir=tmp_path)
    result = orch.play_sub_game(1)
    assert orch.referee.state.status is not GameStatus.ONGOING
    assert result.index == 1


def test_technical_loss_voids_and_reruns(config, tmp_path):
    # Fail on the first turn of sub-game 1, attempt 1 only; rerun must be clean.
    injector = lambda i, a: i == 1 and a == 1  # noqa: E731
    orch = Orchestrator(config, results_dir=tmp_path, failure_injector=injector)
    results = orch.play_series()
    assert len(results) == config.get("num_games")
    assert all(not r.technical_loss for r in results)
