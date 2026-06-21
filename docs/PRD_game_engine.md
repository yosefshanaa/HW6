# PRD — Game Engine, Rules & Referee

**Mechanism PRD** (per submission guidelines §2.3). **Version:** 1.00.
**Parent:** [`PRD.md` §8](PRD.md#8-game-rules-authoritative-summary) · **Design:**
[`PLAN.md` §6–7](PLAN.md#6-game-engine-design).

---

## 1. Description & Theoretical Background

The game engine is the **authoritative referee** for a partially observable, two-agent pursuit game
(Cop vs Thief). It is a deterministic finite state machine: given the current `GameState` and a
**legal** `Action`, it produces the next state, checks for capture/termination, and (at sub-game end)
computes the score. The engine is **pure** — no LLM, no network, no file I/O — so it is fully
unit-testable and reproducible from a seed.

The engine embodies the Dec-POMDP transition function `P` and reward `R` (see
[`PRD_partial_observability.md`](PRD_partial_observability.md) for `Ωᵢ`/`O`).

---

## 2. Specific Requirements

### 2.1 Board & coordinates
- Grid is `grid_size` (default `[5, 5]`), read from config (never hard-coded).
- Coordinates are `[row, col]`, origin `[0, 0]` top-left, rows increase downward, columns increase
  rightward (shared rules §2.3).

### 2.2 Turns & movement
- Turn-based; **Thief moves first**, then Cop, alternating.
- Each turn a player **must** act: move one cell or (Cop only) place a barrier.
- Movement is **8-directional** (king moves; diagonals allowed), exactly one cell.

### 2.3 Barriers
- Cop only; placed on the Cop's **current cell** instead of moving.
- Max **5 per sub-game** (`max_barriers`).
- A barrier cell is impassable to both players.
- A Cop may **not** place a barrier on the Thief's cell or on an existing barrier (shared rules §2.7).
- After placing, the Cop occupies that cell for that turn, is blocked from the next turn on, and
  moves off it on its following turn.

### 2.4 Termination & scoring
- **Capture (Cop win):** Cop and Thief occupy the **same cell**, checked **after each move**. A swap
  (passing through each other in one turn) is **not** capture (shared rules §2.10).
- **Thief win:** Thief survives all **25 moves** (= 25 Thief moves; the Cop's reply to the 25th Thief
  move is the last capture chance — shared rules §2.8).
- **Illegal action** (off-board, into a barrier, a 6th barrier, no action) → that player **loses** the
  sub-game (and, internally, is flagged as a bug to fix).
- Scoring (config-driven): Cop win → Cop `20` / Thief `5`; Thief win → Cop `5` / Thief `10`.
- A series is **6 sub-games**; totals range **30–90** per group.

### 2.5 Referee authority
- One `Referee` owns `GameState` and is the **only** writer.
- Internal game: one referee for both agents. Bonus game: Cop-side engine is referee for its
  sub-games; the other side mirrors and flags mismatches (ADR-004).
- Every accepted/rejected action becomes a `TurnRecord` (auditability).

---

## 3. Input / Output / Performance

| | Spec |
|---|---|
| **Input** | `GameState` + a `TurnPayload` (`role`, `action`, `message`); `action.to = [row,col]` |
| **Output** | New `GameState`, a `TurnResult` (`accepted`/`rejected`+reason, `capture`, `terminal`), and at sub-game end a `SubGameResult` (winner, scores, moves) |
| **Validation** | Bounds; single king-step for `MOVE`; not into a barrier; `BARRIER` only Cop, on own cell, ≤5, not on Thief/existing barrier |
| **Performance** | O(1) per turn (small fixed board); a full 25-move sub-game adjudicated in well under a millisecond (engine only) |
| **Determinism** | Given a seed + fixed actions, the engine is fully reproducible |

---

## 4. Constraints, Alternatives & Decisions

- **Constraint:** all tunables (grid size, max moves, barriers, scoring) come from config (§10).
- **Alternative considered — 4-directional movement:** rejected for the graded series (spec mandates
  8-directional); allowed only as an opt-in warm-up simplifier if **both** bonus teams agree
  (shared rules §2.11).
- **Alternative considered — engine writes its own logs/I/O:** rejected; the engine stays pure and
  the orchestrator/`ReplayStore` handles persistence (keeps the engine testable).
- **Decision:** capture is checked after **every** move (Cop onto Thief, or Thief forced onto Cop),
  never on a swap (ADR-004 + shared rules §2.10).

---

## 5. Success Criteria & Test Scenarios

**Success:** all rules in §2 are enforced and proven by tests; engine is pure and deterministic;
coverage ≥85% for `engine/`.

| # | Scenario | Expected |
|---|---|---|
| T1 | Thief and Cop alternate, Thief first | Move order enforced; wrong-order action rejected |
| T2 | Cop moves onto Thief's cell | Capture → Cop win, Cop 20 / Thief 5 |
| T3 | Thief survives 25 moves | Thief win, Cop 5 / Thief 10 |
| T4 | Diagonal move | Accepted (8-directional) |
| T5 | Two-cell move | Rejected (single step) |
| T6 | Cop places 6th barrier | Rejected → Cop loses |
| T7 | Thief attempts a barrier | Rejected (Cop-only) |
| T8 | Either player steps into a barrier | That player loses |
| T9 | Cop places barrier on Thief's cell / existing barrier | Rejected |
| T10 | Cop and Thief swap cells in one turn | **Not** a capture |
| T11 | Move off-board | Rejected → loser |
| T12 | Series of 6 sub-games | Totals aggregate to 30–90 range |
