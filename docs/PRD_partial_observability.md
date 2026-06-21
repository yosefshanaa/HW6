# PRD — Partial Observability & Dec-POMDP Formulation

**Mechanism PRD** (per submission guidelines §2.3). **Version:** 1.00.
**Parent:** [`PRD.md` §11](PRD.md#11-partial-observability--dec-pomdp-formulation) · **Design:**
[`PLAN.md` §6](PLAN.md#6-game-engine-design).

---

## 1. Description & Theoretical Background

The game is a **decentralized, partially observable** multi-agent system. Neither agent sees the full
board: each sees only its own cell plus whatever lies within a **vision radius**, and otherwise
relies on the opponent's (possibly false) messages and its own memory. This is exactly why the
natural-language channel and bluffing matter.

Formally it is a **Dec-POMDP** (Decentralized Partially Observable Markov Decision Process), the
tuple (assignment §11):

```
⟨ n, S, {Aᵢ}, P, R, {Ωᵢ}, O, γ ⟩
```

| Symbol | Meaning in Cop & Thief |
|---|---|
| **n** | Number of agents = 2 (Cop, Thief) |
| **S** | State space: positions of Cop, Thief, and the set of barriers on the grid |
| **{Aᵢ}** | Per-agent actions: 8 king-moves; Cop also has barrier placement |
| **P** | Transition function: deterministic next state given legal actions |
| **R** | Reward/scoring function: the scoring table (Cop/Thief win values) |
| **{Ωᵢ}** | Per-agent observation space: own cell + within-radius opponent/barriers |
| **O** | Observation function: the referee tool returns each agent's legal view |
| **γ** | Discount factor (used by optional Q-Learning) |

This formalization MUST appear in the README scientific report (assignment §11).

---

## 2. Specific Requirements

### 2.1 Vision model
- Each agent **always** knows its own cell.
- It sees the **opponent** and **barriers** only within `vision_radius` (default **2**), measured by
  **king-move (Chebyshev) distance** on the grid.
- Outside the radius there is **no ground truth** — only messages and memory.
- The referee's `get_observation` tool returns **only** the legal view per agent (never the full
  state).

### 2.2 Chebyshev distance
For cells `a = [r₁,c₁]`, `b = [r₂,c₂]`:

```
chebyshev(a, b) = max(|r₁ − r₂|, |c₁ − c₂|)
```

`b` is visible to the agent at `a` iff `chebyshev(a, b) ≤ vision_radius`.

### 2.3 Start positions
- Cop and Thief are placed so they begin **outside each other's vision radius**
  (`chebyshev(cop, thief) > vision_radius`), and never on the same cell (shared rules §2.9).
- Placement is seeded (shared seed) or fixed-start, selectable via config.

### 2.4 Configurability
- `vision_radius` is a config key (default 2). Both bonus teams may agree to widen it to 3 (nearly
  the whole 5×5) as a spec-compliant simplifier (shared rules §2.11).

---

## 3. Input / Output / Performance

| | Spec |
|---|---|
| **Input** | `GameState`, requesting `role`, `vision_radius` |
| **Output** | `Observation`: `own_cell`, `visible_opponent` (or `None`), `visible_barriers`, `vision_radius`, `move_number` |
| **Leakage guarantee** | Output **never** includes opponent/barriers outside the radius |
| **Performance** | O(grid) to filter visible cells; trivial for 5×5 |

---

## 4. Constraints, Alternatives & Decisions

- **Decision:** use **Chebyshev** (king-move) distance for vision, matching 8-directional movement
  and the shared rules.
- **Alternative — Manhattan/Euclidean radius:** rejected for consistency with king-move movement and
  the shared spec.
- **Alternative — full observability:** rejected; it would remove the Dec-POMDP nature and the point
  of the NL/bluff channel. (Radius 3 is the maximum agreed simplifier, still partial-ish on 5×5.)
- **Constraint:** the observation function is the single guard against information leakage — it is
  tested explicitly.

---

## 5. Success Criteria & Test Scenarios

**Success:** agents only ever receive their legal partial view; start positions satisfy the
out-of-radius invariant; the Dec-POMDP tuple is documented for the README.

| # | Scenario | Expected |
|---|---|---|
| T1 | Opponent at Chebyshev distance ≤ radius | `visible_opponent` populated |
| T2 | Opponent at Chebyshev distance > radius | `visible_opponent = None` |
| T3 | Barrier within radius vs outside | Only within-radius barriers returned |
| T4 | Start placement (seeded) | `chebyshev(cop, thief) > vision_radius`, distinct cells |
| T5 | `vision_radius` changed in config | Visibility changes accordingly, no code edit |
| T6 | Observation never leaks full state | No hidden entity ever appears in output |
