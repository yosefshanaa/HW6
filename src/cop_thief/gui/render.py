"""Pure rendering helpers shared by the terminal + browser GUIs (no I/O state).

Turns game snapshots/observations into board/fog cell grids and embeds a
view-model into the bundled self-contained HTML template. Fully testable.
"""

from __future__ import annotations

import json
from pathlib import Path

_TEMPLATE = Path(__file__).resolve().parent / "web_template.html"


def board_cells(snapshot: dict, grid_size: list[int]) -> list[list[str]]:
    """True board grid: C=cop, T=thief, #=barrier, .=empty (cop drawn last)."""
    rows, cols = grid_size
    cells = [["."] * cols for _ in range(rows)]
    for r, c in snapshot.get("barriers", []):
        cells[r][c] = "#"
    tr, tc = snapshot["thief"]
    cells[tr][tc] = "T"
    cr, cc = snapshot["cop"]
    cells[cr][cc] = "C"
    return cells


def fog_cells(observation: dict, grid_size: list[int]) -> list[list[str]]:
    """Acting agent's fog-of-war grid (?=beyond vision radius)."""
    rows, cols = grid_size
    own = observation["own_cell"]
    radius = observation["vision_radius"]
    me = "C" if observation["role"] == "cop" else "T"
    opp = "T" if me == "C" else "C"
    barriers = {tuple(b) for b in observation.get("visible_barriers", [])}
    opp_cell = observation.get("visible_opponent")
    cells = []
    for r in range(rows):
        row = []
        for c in range(cols):
            if [r, c] == own:
                row.append(me)
            elif max(abs(r - own[0]), abs(c - own[1])) > radius:
                row.append("?")
            elif opp_cell is not None and [r, c] == opp_cell:
                row.append(opp)
            elif (r, c) in barriers:
                row.append("#")
            else:
                row.append(".")
        cells.append(row)
    return cells


def board_to_text(cells: list[list[str]]) -> str:
    """Join a cell grid into the terminal text board."""
    return "\n".join(" ".join(row) for row in cells)


def turn_view(record: dict, grid_size: list[int]) -> dict:
    """Serialize one logged turn into the browser view-model shape."""
    return {
        "move": record["move_number"],
        "role": record["role"],
        "message": record["message"],
        "action": record["action"],
        "board": board_cells(record["resulting_state"], grid_size),
        "fog": fog_cells(record["observation"], grid_size),
    }


def group_rounds(turn_views: list[dict]) -> list[dict]:
    """Group per-turn views into rounds (Thief turn + Cop turn = one round).

    A round opens on each Thief turn; the following Cop turn attaches to it. The
    last round may be Thief-only (the sub-game ended on a Thief action). This is
    the user-facing "step": a sub-game has at most ``max_moves`` rounds (25), not
    50 individual turns.
    """
    rounds: list[dict] = []
    for tv in turn_views:
        if tv["role"] == "thief" or not rounds:
            rounds.append({"n": len(rounds) + 1, "thief": None, "cop": None})
        rounds[-1][tv["role"]] = tv
    return rounds


def build_html(view_model: dict, live: bool = False) -> str:
    """Embed the view-model JSON into the self-contained HTML template.

    ``live`` enables the **Play Again** button (it POSTs to the local GUI
    server). A static export (``--output``) leaves it ``False`` so the page is a
    plain self-contained file with the button hidden.
    """
    template = _TEMPLATE.read_text(encoding="utf-8")
    return (
        template
        .replace("__VIEW_MODEL__", json.dumps(view_model))
        .replace("__LIVE_ENABLED__", "true" if live else "false")
    )
