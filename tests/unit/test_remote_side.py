"""Unit tests for the play-our-half driver's pure logic (no network).

The networked behaviour (concurrent two-peer coordination) is proven live against
the deployed servers; here we lock down the deterministic pieces that decide
correctness: role split, per-(seed,index) starts, attribution, and scoring.
"""

from __future__ import annotations

from cop_thief.domain.records import SubGameResult
from cop_thief.domain.roles import PlayerRole
from cop_thief.match.remote_common import result_for, start_positions
from cop_thief.match.remote_side import RemoteSide
from cop_thief.shared.config import load_config

CFG = load_config()  # 6 games, r2 via match.vision_radius
NULL_CLIENTS = lambda _i: (None, None)  # noqa: E731 - logic tests never touch the clients


def _side(my_group: str) -> RemoteSide:
    return RemoteSide(CFG, my_group, NULL_CLIENTS, group_1="ahk-yosi", group_2="peer")


def test_role_split_swaps_at_the_half():
    us = _side("ahk-yosi")            # group_1: Cop first half, Thief second
    assert [us.my_role(i) for i in range(1, 7)] == (
        [PlayerRole.COP] * 3 + [PlayerRole.THIEF] * 3
    )
    them = _side("peer")             # group_2: the mirror image
    assert [them.my_role(i) for i in range(1, 7)] == (
        [PlayerRole.THIEF] * 3 + [PlayerRole.COP] * 3
    )


def test_starts_are_deterministic_per_index_and_match_across_sides():
    us, them = _side("ahk-yosi"), _side("peer")
    for i in range(1, 7):
        a = start_positions(us.grid_size, us.vision_radius, us.seed, i)
        b = start_positions(us.grid_size, us.vision_radius, us.seed, i)
        assert a == b                                   # stable across reruns
        them_start = start_positions(them.grid_size, them.vision_radius, them.seed, i)
        assert a == them_start                          # both teams derive the same start
        cop, thief = a
        assert cop != thief and cop.chebyshev(thief) > CFG.get("match.vision_radius")


def test_outcome_totals_and_attribution():
    us = _side("ahk-yosi")
    # group_1 wins its 3 Cop games; group_2 wins its 3 Cop games (a 75-75 split).
    us.results = [
        SubGameResult(i, PlayerRole.COP, 5, 20, 5) for i in range(1, 7)
    ]
    outcome = us.outcome()
    assert outcome.totals_by_group == {"ahk-yosi": 75, "peer": 75}
    assert outcome.attribution[0] == {"cop_group": "ahk-yosi", "thief_group": "peer"}
    assert outcome.attribution[5] == {"cop_group": "peer", "thief_group": "ahk-yosi"}


def test_result_reads_winner_and_scores_from_status():
    us = _side("ahk-yosi")
    r = result_for(us.scoring, 2, {"status": "thief_win", "thief_moves": 25})
    assert r.winner is PlayerRole.THIEF and r.moves_played == 25
    assert (r.cop_score, r.thief_score) == (5, 10)  # cop_loss / thief_win
