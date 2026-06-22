"""Lightweight local parameter-sensitivity sweep (no LLM / no credentials).

Runs the autonomous pipeline with the baseline heuristic agents across several
``vision_radius`` and ``grid_size`` settings and prints a Markdown summary
(cop win-rate, average moves). Reproducible from the per-series seeds.

Run:
    uv run python notebooks/parameter_sweep.py
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from cop_thief.domain.roles import PlayerRole
from cop_thief.orchestrator.orchestrator import Orchestrator
from cop_thief.shared.config import Config, load_config


def run_batch(
    base: Config, grid: list[int], radius: int, n_series: int, max_barriers: int | None = None
) -> tuple[int, int, float]:
    """Play ``n_series`` seeded series; return (cop_wins, total, avg_moves)."""
    cop_wins, moves = 0, []
    tmp = Path(tempfile.mkdtemp())
    try:
        for s in range(n_series):
            data = {**base.data, "grid_size": grid, "vision_radius": radius,
                    "seed": 1000 + s, "start_mode": "random"}
            if max_barriers is not None:
                data["max_barriers"] = max_barriers
            cfg = Config(data=data, rate_limits=base.rate_limits)
            for r in Orchestrator(cfg, results_dir=tmp).play_series():
                moves.append(r.moves_played)
                cop_wins += int(r.winner is PlayerRole.COP)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return cop_wins, len(moves), sum(moves) / len(moves)


def main() -> None:
    base = load_config()
    print("### Board / vision sweep\n")
    print("| grid | vision_radius | sub-games | cop win-rate | avg moves |")
    print("|---|---|---|---|---|")
    for grid in ([5, 5], [7, 7]):
        for radius in (1, 2, 3):
            cw, total, avg = run_batch(base, grid, radius, n_series=10)
            print(f"| {grid[0]}x{grid[1]} | {radius} | {total} | {cw / total:.0%} | {avg:.1f} |")

    print("\n### Barrier ablation (cop win-rate with vs. without barriers)\n")
    print("| grid | vision_radius | no barriers | ≤5 barriers |")
    print("|---|---|---|---|")
    for grid, radius in ([5, 5], 2), ([5, 5], 1), ([7, 7], 1):
        off, total, _ = run_batch(base, grid, radius, n_series=10, max_barriers=0)
        on, _, _ = run_batch(base, grid, radius, n_series=10, max_barriers=5)
        print(f"| {grid[0]}x{grid[1]} | {radius} | {off / total:.0%} | {on / total:.0%} |")


if __name__ == "__main__":
    main()
