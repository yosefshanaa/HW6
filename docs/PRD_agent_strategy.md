# PRD — Agent Strategy (Heuristic, Optional Q-Learning, Bluff Handling)

**Mechanism PRD** (per submission guidelines §2.3). **Version:** 1.00.
**Parent:** [`PRD.md` §10](PRD.md#10-agent-behavior--natural-language-communication) · **Design:**
[`PLAN.md` §12](PLAN.md#12-agent-strategy-design).

> **Grading note:** the assignment grades **orchestration**, not strategy (§3, §14). Q-Learning is
> **recommended, not required** (§8). A baseline heuristic fully satisfies the requirement; RL is an
> optional enhancement.

---

## 1. Description & Theoretical Background

Each agent decides a turn from its **partial observation** plus prior (possibly false) messages and
memory. Two strategy paths are supported behind a common `Strategy` base class:

1. **Baseline heuristic (required path).** Distance-driven pursuit/evasion with barrier placement.
2. **Optional tabular Q-Learning (assignment §8).** A simple RL agent that learns a policy over time
   without neural networks.

**Reinforcement-learning primer (assignment §8):** state `s` (where the agent is), action `a` (a
move), reward `r` (quality of the resulting state). The agent learns `Q(s,a)` — the expected
long-run reward of taking `a` in `s` — by trial and error over episodes, using the Bellman update:

```
Q(s,a) ← Q(s,a) + α · [ r + γ · maxₐ′ Q(s′,a′) − Q(s,a) ]
```

with learning rate `α` (e.g., 0.1) and discount `γ` (e.g., 0.9). Example reward shaping from the
spec: small negative per step ("fuel"), large penalty for falling into a pit/illegal move, positive
reward for reaching the goal/capture.

---

## 2. Specific Requirements

### 2.1 Common interface
- `Strategy` base class with `decide(observation, memory) -> Action`; subclasses must not duplicate
  shared logic (no-duplication rule).
- Always returns a **legal** action for the role (the loop must never stall).

### 2.2 Baseline heuristic
- **Cop:** capture if the Thief is one king-step away; else minimize Chebyshev distance to the
  last-known / most-likely Thief cell. Place a barrier (within the ≤5 budget) **only** opportunistically
  — when the Thief is *currently visible*, exactly two cells away, pinned on a board edge, and the Cop
  keeps ≥3 safe exits (so the wall never sacrifices a capture or self-traps).
- **Thief (mobility-aware):** first stay **uncapturable** (≥2 cells from the believed Cop cell), then
  prefer cells with the most escape routes and the greatest clearance from barriers, using raw
  distance and centrality only as tie-breaks. This implements the "avoid barriers and board edges that
  reduce escape options" intent — the earlier *maximize-distance* rule fled into corners and
  self-trapped, which (not the barriers) is what handed the Cop nearly every game.
- Operates on partial info: when the opponent is outside the vision radius, fall back to belief from
  messages + memory.
- **Outcome (deterministic, documented).** On the agreed spec board (5×5, radius 2) equal-speed
  pursuit cannot corner a competent evader, so the Cop must herd with barriers and — on a small,
  near-fully-observed board — reliably wins; balance emerges only when vision is limited relative to
  the board. This is a property of the observation model, not the barrier rule (see
  [`EXPERIMENTS.md`](EXPERIMENTS.md)).

### 2.3 Optional Q-Learning
- State = discretized positions (e.g., agent cell + relative opponent belief); actions = 8 moves
  (+ barrier for Cop). On a 5×5 grid, 25 position states (spec's minimal example).
- ε-greedy exploration; Bellman update as above; reward table configurable.
- No neural networks; a tabular Q (NumPy array) suffices.

### 2.4 Bluff / deception handling
- The opponent's `message` may be false; weight it by a **trust/recency** factor and **never** treat
  it as ground truth.
- Within-radius observations always override messages.
- Our own outgoing `message` may bluff but **must stay well-formed** (schema-valid) so it never
  crashes the opponent's server (shared rules note §3).

---

## 3. Input / Output / Performance

| | Spec |
|---|---|
| **Input** | `Observation` (own cell, within-radius opponent/barriers), recent messages, memory, role |
| **Output** | A legal `Action` (`move`/`barrier`) + an optional `message` string |
| **Heuristic perf** | O(8) candidate moves per turn; negligible CPU |
| **Q-Learning perf** | Tabular update O(1) per step; lightweight; no GPU/deep-learning libs |
| **Robustness** | Always yields a legal action; on uncertainty, conservative default move |

---

## 4. Constraints, Alternatives & Decisions

- **Constraint:** strategy is the *least* graded part — keep it simple, correct, and legal.
- **Alternative — deep RL / neural nets:** **rejected** (overkill; spec explicitly says tabular
  Q-Learning is enough, and RL itself is optional).
- **Alternative — trust messages as truth:** rejected; bluffing is intended, so messages are advisory
  only.
- **Decision:** ship the heuristic as the default; gate Q-Learning behind config so it can be
  enabled for the research/parameter-sensitivity study without risking the autonomous run.

---

## 5. Success Criteria & Test Scenarios

**Success:** every decision is a legal action on partial observations; the heuristic completes full
sub-games without the orchestrator ever needing the illegal-action fallback; (if enabled) Q-Learning
trains on a toy run and improves average reward.

| # | Scenario | Expected |
|---|---|---|
| T1 | Opponent within radius | Cop closes distance / Thief opens distance |
| T2 | Opponent outside radius | Decide from messages+memory; still legal |
| T3 | Cop near barrier budget | Places barriers only while ≤5 and useful |
| T4 | Deceptive message received | Decision not dictated by the message alone |
| T5 | Edge/corner position | No illegal off-board action proposed |
| T6 | Q-update step (if enabled) | `Q(s,a)` moves toward the TD target |
| T7 | Long run, heuristic only | Zero illegal actions across a full series |
