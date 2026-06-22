"""Partial-observation + start-placement tests (PRD_partial_observability §5)."""

from __future__ import annotations

import random

import pytest

from cop_thief.domain.barrier import Barrier
from cop_thief.domain.position import Position
from cop_thief.domain.roles import PlayerRole
from cop_thief.engine.observation_service import (
    compute_observation,
    fixed_start,
    random_start,
)
from cop_thief.engine.referee import Referee

SCORING = {"cop_win": 20, "thief_win": 10, "cop_loss": 5, "thief_loss": 5}


def make_state(cop, thief, vision=2):
    ref = Referee([5, 5], 25, 5, SCORING, vision)
    return ref.reset(cop, thief)


def test_opponent_visible_within_radius():
    state = make_state(Position(2, 2), Position(2, 3))
    obs = compute_observation(state, PlayerRole.COP, vision_radius=2)
    assert obs.visible_opponent == Position(2, 3)


def test_opponent_hidden_outside_radius():
    state = make_state(Position(0, 0), Position(4, 4))
    obs = compute_observation(state, PlayerRole.COP, vision_radius=2)
    assert obs.visible_opponent is None


def test_barriers_filtered_by_radius():
    state = make_state(Position(2, 2), Position(0, 0))
    state.barriers = [
        Barrier(Position(2, 3), PlayerRole.COP, 0),   # chebyshev 1 from (2,2): visible at r=1
        Barrier(Position(0, 0), PlayerRole.COP, 0),   # chebyshev 2 from (2,2): hidden at r=1
    ]
    obs = compute_observation(state, PlayerRole.COP, vision_radius=1)
    assert Position(2, 3) in obs.visible_barriers
    assert Position(0, 0) not in obs.visible_barriers


def test_observation_never_leaks_hidden_opponent_in_dict():
    state = make_state(Position(0, 0), Position(4, 4))
    obs = compute_observation(state, PlayerRole.COP, vision_radius=2)
    assert obs.as_dict()["visible_opponent"] is None


def test_random_start_outside_radius_and_distinct():
    rng = random.Random(1234)
    cop, thief = random_start([5, 5], vision_radius=2, rng=rng)
    assert cop != thief
    assert cop.chebyshev(thief) > 2


def test_random_start_is_seed_reproducible():
    a = random_start([5, 5], 2, random.Random(99))
    b = random_start([5, 5], 2, random.Random(99))
    assert a == b


def test_random_start_raises_when_impossible():
    with pytest.raises(ValueError):
        random_start([1, 1], vision_radius=2, rng=random.Random(0))


def test_random_start_respects_max_distance():
    """With a start-distance cap every pair is in (vision_radius, max_distance]."""
    rng = random.Random(7)
    for _ in range(200):
        cop, thief = random_start([5, 5], vision_radius=1, rng=rng, max_distance=3)
        assert 2 <= cop.chebyshev(thief) <= 3


def test_random_start_raises_when_band_empty():
    """An impossible band (max_distance <= vision_radius) raises, never dead-ends."""
    with pytest.raises(ValueError):
        random_start([5, 5], vision_radius=1, rng=random.Random(0), max_distance=1)


def test_fixed_start_reads_config():
    cop, thief = fixed_start({"cop": [0, 0], "thief": [4, 4]})
    assert cop == Position(0, 0)
    assert thief == Position(4, 4)
