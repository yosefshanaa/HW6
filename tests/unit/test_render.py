"""Pure render-helper tests for the GUIs (PRD_gui_and_logs)."""

from __future__ import annotations

import json

from cop_thief.gui.render import (
    board_cells,
    board_to_text,
    build_html,
    fog_cells,
    group_rounds,
    turn_view,
)


def test_board_cells_places_markers():
    cells = board_cells({"cop": [0, 0], "thief": [4, 4], "barriers": [[2, 2]]}, [5, 5])
    assert cells[0][0] == "C"
    assert cells[4][4] == "T"
    assert cells[2][2] == "#"
    assert cells[1][1] == "."


def test_board_cells_capture_shows_cop_over_thief():
    cells = board_cells({"cop": [1, 1], "thief": [1, 1], "barriers": []}, [3, 3])
    assert cells[1][1] == "C"  # cop drawn last on capture


def test_fog_cells_masks_beyond_radius():
    obs = {"role": "cop", "own_cell": [0, 0], "vision_radius": 1,
           "grid_size": [5, 5], "visible_opponent": None, "visible_barriers": []}
    cells = fog_cells(obs, [5, 5])
    assert cells[0][0] == "C"
    assert cells[4][4] == "?"      # beyond radius
    assert cells[1][1] == "."      # within radius, empty


def test_fog_cells_shows_visible_opponent_and_barrier():
    obs = {"role": "thief", "own_cell": [2, 2], "vision_radius": 2,
           "grid_size": [5, 5], "visible_opponent": [2, 3], "visible_barriers": [[3, 3]]}
    cells = fog_cells(obs, [5, 5])
    assert cells[2][2] == "T"
    assert cells[2][3] == "C"
    assert cells[3][3] == "#"


def test_board_to_text_roundtrip():
    text = board_to_text([["C", "."], [".", "T"]])
    assert text == "C .\n. T"


def test_turn_view_serializes_record():
    record = {
        "sub_game": 1, "move_number": 3, "role": "thief",
        "message": "going north", "action": {"type": "move", "to": [2, 3]},
        "observation": {"role": "thief", "own_cell": [2, 2], "vision_radius": 2,
                        "grid_size": [5, 5], "visible_opponent": None, "visible_barriers": []},
        "resulting_state": {"cop": [0, 0], "thief": [2, 3], "barriers": []},
    }
    view = turn_view(record, [5, 5])
    assert view["move"] == 3
    assert view["role"] == "thief"
    assert view["action"] == {"type": "move", "to": [2, 3]}
    assert view["board"][2][3] == "T"
    assert isinstance(view["fog"], list) and len(view["fog"]) == 5


def _tv(role, move, to):
    return {"move": move, "role": role, "message": role + " msg",
            "action": {"type": "move", "to": to},
            "board": [[".", "."]], "fog": [[".", "."]]}


def test_group_rounds_pairs_thief_then_cop():
    turns = [_tv("thief", 0, [1, 1]), _tv("cop", 0, [0, 1]),
             _tv("thief", 1, [2, 2]), _tv("cop", 1, [1, 2])]
    rounds = group_rounds(turns)
    assert len(rounds) == 2                        # 4 turns -> 2 rounds (not 4 steps)
    assert rounds[0]["n"] == 1
    assert rounds[0]["thief"]["role"] == "thief"
    assert rounds[0]["cop"]["role"] == "cop"


def test_group_rounds_trailing_thief_only():
    turns = [_tv("thief", 0, [1, 1]), _tv("cop", 0, [0, 1]), _tv("thief", 1, [2, 2])]
    rounds = group_rounds(turns)
    assert len(rounds) == 2
    assert rounds[1]["thief"] is not None
    assert rounds[1]["cop"] is None                # sub-game ended on the Thief's move


def test_build_html_embeds_view_model():
    vm = {"grid_size": [5, 5], "totals": {"cop": 20, "thief": 5},
          "sub_games": [{"index": 1, "winner": "cop", "cop_score": 20,
                         "thief_score": 5, "moves_played": 4, "rounds": []}]}
    html = build_html(vm)
    assert "__VIEW_MODEL__" not in html           # placeholder replaced
    assert "Cop &amp; Thief" in html
    assert 'id="board"' in html
    assert json.dumps(vm) in html                 # exact data embedded


def test_build_html_live_flag_controls_play_again():
    vm = {"grid_size": [5, 5], "totals": {"cop": 0, "thief": 0}, "sub_games": []}
    live = build_html(vm, live=True)
    static = build_html(vm)                        # default: static export
    assert "__LIVE_ENABLED__" not in live and "__LIVE_ENABLED__" not in static
    assert "const LIVE = true" in live             # live: Play Again active
    assert "const LIVE = false" in static          # static: hidden (can't run Python)
    assert 'id="again"' in live and 'id="again"' in static   # button present in the markup
    assert "let DATA =" in live                    # DATA is mutable so Play Again can replace it
