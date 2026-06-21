"""Tests for the Position domain model."""

from __future__ import annotations

from cop_thief.domain.position import Position


def test_chebyshev_distance():
    assert Position(0, 0).chebyshev(Position(2, 1)) == 2
    assert Position(4, 4).chebyshev(Position(4, 4)) == 0


def test_in_bounds():
    assert Position(0, 0).in_bounds([5, 5])
    assert Position(4, 4).in_bounds([5, 5])
    assert not Position(5, 0).in_bounds([5, 5])
    assert not Position(-1, 0).in_bounds([5, 5])


def test_neighbors8_count_and_membership():
    n = Position(2, 2).neighbors8()
    assert len(n) == 8
    assert Position(1, 1) in n and Position(3, 3) in n
    assert Position(2, 2) not in n


def test_is_king_step_to():
    assert Position(2, 2).is_king_step_to(Position(3, 3))  # diagonal
    assert Position(2, 2).is_king_step_to(Position(2, 3))  # orthogonal
    assert not Position(2, 2).is_king_step_to(Position(2, 4))  # two cells
    assert not Position(2, 2).is_king_step_to(Position(2, 2))  # same cell


def test_serialization_roundtrip():
    assert Position(3, 1).as_list() == [3, 1]
    assert Position.from_list([3, 1]) == Position(3, 1)
