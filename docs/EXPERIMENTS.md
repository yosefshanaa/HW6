# Experiments & Parameter Sensitivity

**Scope:** lightweight, fully local experiments using the **baseline heuristic agents** (no LLM, no
credentials). Reproducible from per-series seeds. This supports the research/analysis requirement
(guidelines §9); richer charts and an LLM-driven study are pending (see *External inputs* in
[`TODO.md`](TODO.md#external-inputs-needed)).

> **Reminder:** the graded core is orchestration/engineering, not win-rate. These results
> characterize the *engine + heuristic*, not a tuned game AI.

---

## 1. Method

`notebooks/parameter_sweep.py` runs the autonomous pipeline (mobility-aware Thief, pursuit + tactical
barrier Cop) across a grid of `(grid_size, vision_radius)` settings. For each cell it plays **10
seeded series × 6 sub-games = 60 sub-games** (seeds 1000–1009, `start_mode: random`) and records the
**Cop win-rate** and **average moves**. A second pass repeats three cells with barriers **off**
(`max_barriers: 0`) vs. **on** (≤5) to isolate the barrier mechanic. Everything else is the config
default (8-directional movement, max 25 moves, scoring 20/5 · 5/10).

Reproduce:

```bash
uv run python notebooks/parameter_sweep.py
```

## 2. Results (60 sub-games per cell)

| grid | vision_radius | sub-games | cop win-rate | avg moves |
|---|---|---|---|---|
| 5x5 | 1 | 60 | 67% | 9.4 |
| 5x5 | 2 | 60 | 100% | 7.9 |
| 5x5 | 3 | 60 | 100% | 8.2 |
| 7x7 | 1 | 60 | 52% | 13.2 |
| 7x7 | 2 | 60 | 100% | 10.7 |
| 7x7 | 3 | 60 | 100% | 11.6 |

### Barrier ablation (Cop win-rate with vs. without barriers)

| grid | vision_radius | no barriers | ≤5 barriers |
|---|---|---|---|
| 5x5 | 2 | **0%** | **100%** |
| 5x5 | 1 | 67% | 67% |
| 7x7 | 1 | 52% | 52% |

> The 67%→67% at r1 is **not** "barriers don't matter" — at radius 1 the Cop
> places **zero** barriers (measured). The barrier trigger needs the Thief
> *visible at distance 2*, which radius-1 vision can never supply. Barriers are
> **inoperative** under r1 fog, **decisive** at r2.

### Barrier-budget & decay sensitivity (5×5 r2, balance audit)

Every knob on the fixed 5×5 is a **cliff** — there is no smooth strategy setting
near 50%, which is why balance comes from the vision radius, not from tuning the
barrier rule:

| lever (5×5 r2) | cop win-rate |
|---|---|
| Cop barrier budget ≤1 / sub-game | 10% |
| Cop barrier budget ≤2 | 97% |
| temporary barriers, decay after 2 thief-moves | 33% |
| temporary barriers, decay after 3+ thief-moves | 100% |
| randomized Thief tie-breaks | 100% |

## 3. Interpretation — what actually balances the game

This sweep answers a design question raised during review: *the Cop won nearly every game — was the
barrier heuristic overpowered?* The honest finding is **no — the dominant factor is the observation
model, not the barriers**:

- **The old imbalance was a Thief bug.** The previous Thief greedily maximised distance and fled
  straight into corners, self-trapping. It has been replaced by a **mobility-aware** evader (stay
  uncapturable, then keep open space and clearance from walls). That alone is the real "rebalance".
- **Vision relative to board size decides the contest.** When the Cop can effectively see the whole
  board (radius **2 or 3** on these small grids), it tracks the Thief continuously and a competent
  Thief cannot survive 25 moves → **100% Cop**. When vision is genuinely limited (**radius 1**), the
  Thief breaks contact and exploits the fog → **52–67% Cop**, a balanced contest.
- **Barriers are decisive at r2, inoperative at r1 — not "incidental".** The ablation is the clearest
  signal: at **5×5 r2** pursuit *alone* catches the mobility-aware Thief **0%** of the time (equal-speed
  king-move pursuit cannot corner a competent evader), so the Cop *must* herd with barriers, and on a
  near-fully-observed board that herding always completes (0% → 100%). The barrier heuristic is
  therefore the **decisive mechanism** at r2 — necessary *and* sufficient — not a sideshow. At **r1**
  the table reads 67%→67% only because barriers **never fire** (the trigger needs a Thief visible at
  distance 2, which r1 vision can't supply): they are **visibility-gated**, decisive where the Cop sees
  two cells out, dormant under real fog. The heuristic itself is still selective (capture-first, only an
  edge-pinned Thief at distance 2, budget-capped, never self-trapping; see `PRD_agent_strategy`).

**Conclusion / what we ship.** The contest is governed by **vision relative to board size**, and on
the **fixed** 5×5 the only lever that yields a balanced game is the (team-chosen, *not* rule-fixed)
**vision radius** — every strategy/budget knob is bimodal (budget 1→2 flips 10%→97%; decay 2→3 flips
33%→100%; randomising the Thief stays 100%; see the sensitivity table above). We therefore **ship the
local series at radius 1** (~67% Cop, with genuine Thief escapes) as the default. The **bonus
inter-group match** keeps the agreed **radius 2** (`SHARED_MATCH_RULES` §2.9, via `match.vision_radius`),
where the game is structurally **Cop-favoured** — expected pursuit-evasion on a near-fully-observed
board, and *symmetric* across the role split, so the bonus stays fair even though it is Cop-dominated.

## 4. Threats to validity

- Heuristic-only: results reflect the simple pursuit/evasion policies, not LLM agents.
- Both policies are **deterministic**, so each `(start, config)` has one outcome; the win-rate is the
  fraction of *start positions* the Cop wins, over 10 seeds/cell — a small sample. Widen `n_series`
  for tighter estimates (1 series/cell ≈ ±13pp).
- Outcomes are sensitive to strategy tie-breaks on this tiny grid; the policies use **principled**,
  documented tie-breaks (open space, then centre) rather than ones tuned to the result.

## 5. Planned extensions (need inputs / more time)

- Charts (win-rate vs. radius, move-count distributions) rendered to `assets/` via a notebook.
- LLM-agent vs. heuristic comparison + **token cost** capture (needs an LLM key — see
  [`COST_ANALYSIS.md`](COST_ANALYSIS.md)).
