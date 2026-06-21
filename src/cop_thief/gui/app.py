"""Minimal text visualization / replay (PRD_gui_and_logs; CLI fallback GUI).

Calls the SDK for live runs and the ReplayStore for stored series. This is a
lightweight fallback renderer; a richer GUI can replace it later. Excluded from
coverage (visualization layer).
"""

from __future__ import annotations

import argparse

from cop_thief.gui.render import board_cells, board_to_text, fog_cells
from cop_thief.sdk.sdk import CopThiefSDK
from cop_thief.shared.replay import ReplayStore


def render_board(snapshot: dict, grid_size: list[int]) -> str:
    """Render a board snapshot as text (C=cop, T=thief, #=barrier, .=empty)."""
    return board_to_text(board_cells(snapshot, grid_size))


def render_fog(observation: dict, grid_size: list[int]) -> str:
    """Render the acting agent's fog-of-war view (`?`=unknown beyond radius)."""
    return board_to_text(fog_cells(observation, grid_size))


def replay_file(path: str, grid_size: list[int]) -> None:
    """Print every logged turn of a stored sub-game (true board + agent's fog)."""
    for record in ReplayStore(path).load():
        print(f"\n[sub-game {record['sub_game']} move {record['move_number']} "
              f"{record['role']}] {record['message']}")
        print("true board:")
        print(render_board(record["resulting_state"], grid_size))
        print(f"{record['role']} fog-of-war view:")
        print(render_fog(record["observation"], grid_size))


def main() -> None:
    """Run a live series (printing the final board per sub-game) or replay a file."""
    parser = argparse.ArgumentParser(description="Cop & Thief — text visualization.")
    parser.add_argument("--replay", default=None, help="path to a sub-game JSONL log")
    args = parser.parse_args()
    sdk = CopThiefSDK()
    grid = sdk.config.get("grid_size")
    if args.replay:
        replay_file(args.replay, grid)
        return
    results, series_dir = sdk.run_series()
    for r in results:
        print(f"\nSub-game {r.index}: {r.winner.value} wins "
              f"(cop {r.cop_score} / thief {r.thief_score})")
    print(f"\nLogs: {series_dir}")


if __name__ == "__main__":
    main()
