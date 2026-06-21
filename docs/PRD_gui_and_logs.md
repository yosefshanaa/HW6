# PRD — GUI, Visualization, Logging & Replay

**Mechanism PRD** (per submission guidelines §2.3). **Version:** 1.00.
**Parent:** [`PRD.md` §16–17](PRD.md#16-logging--auditability-requirements) · **Design:**
[`PLAN.md` §16–17](PLAN.md#16-logging-and-replay-design).

---

## 1. Description & Theoretical Background

Two related concerns:

1. **Auditability/logging.** Every message and action is timestamped and persisted so any sub-game
   can be **replayed** and so logs can be swapped with the partner team for joint debugging
   (assignment §11; shared rules §3).
2. **Visualization/GUI.** A GUI (or rich-CLI fallback) renders the match for humans: the board,
   agents, barriers, whose turn it is, each agent's fog-of-war observation, the exchanged
   natural-language messages, running scores, and a live log (assignment §12; guidelines §10).

The GUI calls the **SDK** only (never internal business logic) per guidelines §4.1.

---

## 2. Specific Requirements

### 2.1 Logging & replay
- Persist one **`TurnRecord`** per turn: `timestamp`, `sub_game`, `move_number`, `role`,
  `observation`, `message`, `action`, `validation` (accepted/rejected + reason), `resulting_state`.
- Storage format: **JSONL** under `results/<series-id>/`.
- All external API calls (LLM, Gmail, peer MCP) are logged through the API Gatekeeper.
- A **replay** loads a series JSONL and re-renders it identically (no LLM/network needed).
- Logs are structured and swappable with the partner team after the bonus match.

### 2.2 GUI views (or rich-CLI equivalent)
- **Board view:** grid; Cop, Thief, and barrier markers; coordinates `[row,col]`.
- **Turn indicator:** whose move it is and the move number / max.
- **Observation panels:** each agent's fog-of-war view (only within `vision_radius`).
- **Message log:** the natural-language `message`s (with a hint that they may bluff).
- **Score panel:** running Cop/Thief scores and sub-game index.
- **Event log:** scrollable, timestamped turn records.
- **Replay mode:** step/auto-play a stored series.

### 2.3 Quality
- Follows **Nielsen's 10 usability heuristics**; clear status visibility and error messages.
- Screenshots of each major view captured into `assets/`/`results/` for the report (guidelines §10).
- GUI failure must **not** stop a headless series (graceful degradation); logging always continues.

### 2.4 Research visualization (guidelines §9)
- Charts for the scientific report: learning curves (if Q-Learning), parameter-sensitivity plots,
  heatmaps of positions/captures, score distributions — generated from the logs in `notebooks/`.

---

## 3. Input / Output / Performance

| | Spec |
|---|---|
| **Log input** | `TurnRecord`s from the orchestrator (live) |
| **Log output** | JSONL per series in `results/`; replayable |
| **GUI input** | `MatchStatus` + `TurnRecord`s via the SDK |
| **GUI output** | Rendered board/observations/messages/scores/logs; screenshots |
| **Performance** | Rendering keeps up with the (LLM-paced) turn loop; replay is instant |
| **Coverage note** | GUI module excluded from coverage (`omit` in `pyproject.toml`), per guidelines |

---

## 4. Constraints, Alternatives & Decisions

- **Decision:** GUI calls the SDK only; a **rich-CLI fallback** renders the same information so the
  visualization requirement is met even without a GUI toolkit.
- **Alternative — GUI reads engine state directly:** rejected; violates the SDK boundary.
- **Constraint:** logging is on the critical path (auditability is a MUST); the GUI is a SHOULD and
  must never block the autonomous run.
- **Decision:** JSONL chosen for logs — append-friendly, line-replayable, easy to diff/swap with the
  partner team.

---

## 5. Success Criteria & Test Scenarios

**Success:** every message+action is timestamped and logged; any sub-game replays exactly from JSONL;
the GUI/CLI shows board, agents, barriers, turns, observations, messages, scores, and logs; GUI
failure doesn't stop a run.

| # | Scenario | Expected |
|---|---|---|
| T1 | Play a turn | A `TurnRecord` with all fields is appended to JSONL |
| T2 | Replay a stored series | Re-renders identically; no LLM/network calls |
| T3 | Render fog-of-war | Observation panel hides out-of-radius entities |
| T4 | Bluff message displayed | Shown in message log; doesn't change scores |
| T5 | Kill the GUI mid-run | Headless series continues; logs keep flowing |
| T6 | Generate report charts | Notebook produces charts from `results/` logs |
| T7 | Swap logs with partner | JSONL is self-contained and parseable by the other team |
