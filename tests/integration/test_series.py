"""End-to-end series orchestration tests (PRD §6.6, acceptance criteria)."""

from __future__ import annotations

import copy
import json

from cop_thief.constants import ActionType, GameStatus
from cop_thief.domain.roles import PlayerRole
from cop_thief.orchestrator.orchestrator import Orchestrator
from cop_thief.shared.config import Config


def _with(config, **overrides):
    """A copy of ``config`` with top-level keys overridden (for sweeps in tests)."""
    data = copy.deepcopy(config.data)
    data.update(overrides)
    return Config(data=data, rate_limits=config.rate_limits)


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


def test_all_logged_actions_are_legal(config, tmp_path):
    """Every committed turn in a full series is a legal action (never an illegal loss)."""
    Orchestrator(config, results_dir=tmp_path).play_series()
    for log in tmp_path.glob("*/sub_game_*.jsonl"):
        for line in log.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            assert rec["validation"]["accepted"] is True, rec["validation"]


def test_cop_dominance_is_observation_driven_not_a_barrier_bug(config, tmp_path):
    """The Cop's edge on the spec board comes from near-full visibility, not a rigged
    barrier: with vision limited relative to the board (radius 1) the Thief wins
    sub-games, so a default run is not trivially always-Cop because of barriers."""
    r1 = _with(config, vision_radius=1)
    results = Orchestrator(r1, results_dir=tmp_path).play_series()
    assert any(r.winner is PlayerRole.THIEF for r in results)


def test_cop_uses_barriers_opportunistically_not_every_turn(config, tmp_path):
    """At the bonus radius (2, where the Cop can see a distance-2 Thief) the Cop
    both places tactical barriers AND takes plain moves on most turns — barriers
    are a real tool used as the exception, never every turn. (At the radius-1
    local default the Cop never sees a distance-2 Thief, so it places none.)"""
    r2 = _with(config, vision_radius=2)
    Orchestrator(r2, results_dir=tmp_path).play_series()
    cop_moves = cop_barriers = 0
    for log in tmp_path.glob("*/sub_game_*.jsonl"):
        for line in log.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            if rec["role"] != PlayerRole.COP.value:
                continue
            if rec["action"]["type"] == ActionType.BARRIER.value:
                cop_barriers += 1
            else:
                cop_moves += 1
    assert cop_barriers > 0  # barriers are genuinely used at radius 2
    assert cop_moves > cop_barriers  # but mostly pursuit; barriers are the exception


def test_barrier_turns_are_single_action_in_logs(config, tmp_path):
    """Authoritative JSONL proof: every Cop barrier turn places a barrier on the
    Cop's own cell and does NOT also move the Cop (one committed action/turn).
    Uses radius 2 so the Cop actually exercises barriers."""
    Orchestrator(_with(config, vision_radius=2), results_dir=tmp_path).play_series()
    saw_barrier = False
    for log in sorted(tmp_path.glob("*/sub_game_*.jsonl")):
        prev_cop = None
        for line in log.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            post = rec["resulting_state"]["cop"]
            if (rec["role"] == PlayerRole.COP.value
                    and rec["action"]["type"] == ActionType.BARRIER.value):
                saw_barrier = True
                assert rec["action"]["to"] == post           # barrier on the Cop's cell
                assert prev_cop is None or post == prev_cop   # Cop did not move
            prev_cop = post
    assert saw_barrier, "no barrier turn was exercised — test scenario is vacuous"


def test_no_degenerate_cop_oscillation_loop(config, tmp_path):
    """Regression for the reported loop: across a default seed sweep, no sub-game
    leaves the Cop bouncing between only one or two cells for the whole game."""
    for seed in range(1000, 1006):
        Orchestrator(_with(config, seed=seed, start_mode="random"),
                     results_dir=tmp_path / str(seed)).play_series()
    for log in tmp_path.glob("*/*/sub_game_*.jsonl"):
        cop_cells = [tuple(json.loads(line)["resulting_state"]["cop"])
                     for line in log.read_text(encoding="utf-8").splitlines()
                     if json.loads(line)["role"] == PlayerRole.COP.value]
        if len(cop_cells) >= 8:
            assert len(set(cop_cells)) >= 3, f"Cop looped in {log}: {cop_cells}"


def test_default_config_series_is_balanced_not_all_cop(config, tmp_path):
    """The shipped LOCAL default (radius 1 + start_distance_max) must be a real,
    roughly even contest over a seed sweep — not a Cop sweep. Guards against
    regressing to a near-fully-observed board (radius 2) or pathological
    far-corner starts that hand the game to one side."""
    cop = thief = 0
    for seed in range(1000, 1030):
        cfg = _with(config, seed=seed, start_mode="random")
        for r in Orchestrator(cfg, results_dir=tmp_path).play_series():
            if r.winner is PlayerRole.COP:
                cop += 1
            else:
                thief += 1
    assert cop >= 1 and thief >= 1, f"one side never wins ({cop} cop / {thief} thief)"
    rate = cop / (cop + thief)
    assert 0.4 <= rate <= 0.6, f"cop win-rate {rate:.0%} outside the balanced 40-60% band"


def test_r2_remains_cop_favoured(config, tmp_path):
    """The agreed bonus radius (2, unbounded starts) stays Cop-favoured. The local
    balance fix (radius 1 + start cap) must NOT silently alter the bonus-match
    assumptions, and must not weaken the engine."""
    r2 = _with(config, vision_radius=2, start_distance_max=None)
    cop = thief = 0
    for seed in range(1000, 1003):
        cfg = _with(r2, seed=seed, start_mode="random")
        for r in Orchestrator(cfg, results_dir=tmp_path).play_series():
            cop += r.winner is PlayerRole.COP
            thief += r.winner is PlayerRole.THIEF
    assert cop / (cop + thief) >= 0.9, f"r2 unexpectedly not Cop-favoured ({cop}/{cop + thief})"
