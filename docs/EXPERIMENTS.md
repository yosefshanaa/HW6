# Experiments & Parameter Sensitivity

**Scope:** lightweight, fully local experiments using the **baseline heuristic agents** (no LLM, no
credentials). Reproducible from per-series seeds. This supports the research/analysis requirement
(guidelines §9); richer charts and an LLM-driven study are pending (see *External inputs* in
[`TODO.md`](TODO.md#external-inputs-needed)).

> **Reminder:** the graded core is orchestration/engineering, not win-rate. These results
> characterize the *engine + heuristic*, not a tuned game AI.

---

## 1. Method

`notebooks/parameter_sweep.py` runs the autonomous pipeline across a grid of `(grid_size,
vision_radius)` settings. For each cell it plays **10 seeded series × 6 sub-games = 60 sub-games**
(seeds 1000–1009, `start_mode: random`) and records the **Cop win-rate** and **average moves**
(Thief moves before termination). Everything else is the config default (8-directional movement,
max 25 moves, scoring 20/5 · 5/10).

Reproduce:

```bash
uv run python notebooks/parameter_sweep.py
```

## 2. Results (60 sub-games per cell)

| grid | vision_radius | sub-games | cop win-rate | avg moves |
|---|---|---|---|---|
| 5x5 | 1 | 60 | 88% | 4.9 |
| 5x5 | 2 | 60 | 97% | 4.7 |
| 5x5 | 3 | 60 | 53% | 14.3 |
| 7x7 | 1 | 60 | 45% | 14.6 |
| 7x7 | 2 | 60 | 82% | 9.3 |
| 7x7 | 3 | 60 | 58% | 14.4 |

## 3. Interpretation

- **Board size dominates.** On the small 5×5 board the Cop usually wins quickly (≈5 moves); on 7×7
  the Thief has far more room, so win-rate drops and games run longer.
- **Vision is non-monotonic** because of the **start-distance constraint** (`PRD_partial_observability`
  §2.3): start cells must be **outside** each other's `vision_radius`. A larger radius forces a
  *larger initial separation*. On 5×5, radius 3 forces near-corner starts (Chebyshev = 4), handing
  the Thief maximal initial distance — so the Cop's win-rate falls from 97% (r=2) to 53% (r=3) and
  games lengthen (4.7 → 14.3 avg moves). On 7×7, r=1 leaves the Cop effectively blind at the start
  (45%); r=2 is the sweet spot (82%).
- **Engineering takeaway:** the default **5×5 / radius 2** gives decisive, short games — good for
  fast, deterministic CI/demo runs — while **7×7 / radius 2–3** produces longer, more contested
  games useful for stress-testing the orchestration (timeouts, logging volume, Technical-Loss
  reruns).

## 4. Threats to validity

- Heuristic-only: results reflect the simple pursuit/evasion policy, not LLM agents.
- The Cop baseline does **not** place barriers, so the barrier mechanic is unexercised here (it is
  covered by engine tests). Enabling barrier heuristics would likely raise Cop win-rate on larger
  boards.
- 10 series/cell is a small sample; widen `n_series` for tighter estimates.

## 5. Planned extensions (need inputs / more time)

- Charts (win-rate vs. radius, move-count distributions) rendered to `assets/` via a notebook.
- Barrier-usage ablation (Cop with/without barrier placement).
- LLM-agent vs. heuristic comparison + **token cost** capture (needs an LLM key — see
  [`COST_ANALYSIS.md`](COST_ANALYSIS.md)).
