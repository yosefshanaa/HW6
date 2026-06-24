# Shared Match Rules — HW6 Cop & Thief (Dual AI Agents via MCP)

**One common spec for two friendly teams.** This is **not** a contract — it's the shared
reference both teams build against, so the two systems speak the same language and the match
runs smoothly. Bonus inter‑group match per Dr. Yoram Segal's spec, §12.

| | Value |
|---|---|
| Team A | `__________` |
| Team B | `__________` |
| When | `__________` (within 1 week of publication) |
| Timezone | `Asia/Jerusalem` |
| Spec version | `1.00` |

---

## 0. How to read this

- **FIXED** = comes from the assignment, identical for everyone. Listed so both teams build it
  the same way.
- **PICK TOGETHER ☐** = a detail the spec leaves open. Choose **one** value so the two engines
  match. A sensible default is given — keep it or change it together, then tick it.

---

## 1. The game (FIXED)

- Grid **5×5**, **8‑directional** movement (diagonals allowed), one cell per move. Grid size
  read from config.
- **Sub‑game = max 25 moves.** Turn‑based, **thief moves first**, then cop, repeat.
- Every turn a player **must** either **move one cell** or (cop only) **place a barrier**.
- **Barrier:** cop places it on one of its **8 adjacent empty cells** (lecturer‑confirmed; the cop
  stays put) instead of moving; **max 5 per sub‑game**; thief can't place barriers; the cell becomes
  **impassable for both**; **stepping into a barrier = that player loses.**
- **Cop wins** = lands on the thief's cell. **Thief wins** = survives all 25 moves.
- **Full series = 6 sub‑games**, role split fixed by the spec:
  - Sub‑games **1–3:** Team A **cop** vs Team B **thief**.
  - Sub‑games **4–6:** Team B **cop** vs Team A **thief**.
- **Scoring per sub‑game:**

  | Result | Cop player | Thief player |
  |---|---|---|
  | Cop wins (capture) | **20** | 5 |
  | Thief wins (escape) | 5 | **10** |

- Agents talk in **free natural language** (bluffing/deception is part of the game); positions
  are validated via **MCP tools**.
- The game is **partially observable** (Dec‑POMDP): an agent sees only within a **vision radius**
  and otherwise relies on the (possibly false) messages. Radius value → §2.9.

---

## 2. Details to line up so both engines match

### 2.1 Single source of truth for the board
So the two engines never disagree about where things are:
- **PICK TOGETHER ☐** One **referee** owns the authoritative state. For sub‑games where Team A
  is cop, **Team A's engine is referee**; where Team B is cop, **Team B's engine is referee**.
  The other side mirrors it and flags any mismatch so you can fix it together.
- *Or:* one shared referee process for all 6 sub‑games: `__________`.

### 2.2 Message + action per turn (keeps natural‑language talk, stays unambiguous)
Each turn has a free **`message`** (the talk, may bluff) and a structured **`action`** the
referee checks. The result is decided on the `action`, not the text.
- **PICK TOGETHER ☐** Turn shape:
  ```json
  {
    "sub_game": 1,
    "move_number": 7,
    "role": "thief",
    "message": "free natural-language text (optional, may bluff)",
    "action": { "type": "move|barrier", "to": [row, col] }
  }
  ```

### 2.3 Coordinate convention
- **PICK TOGETHER ☐** Origin **`[0,0]` top‑left**, addressing **`[row, col]`**, rows down,
  cols right. (If the two engines disagree here, everything silently breaks.)

### 2.4 Starting positions
- **PICK TOGETHER ☐** Random per sub‑game from a **shared seed** announced beforehand; seed =
  `__________`. Cop and thief never start on the same cell.
- *Or:* fixed — cop `[__,__]`, thief `[__,__]`.

### 2.5 Per‑turn time
- **PICK TOGETHER ☐** **30 seconds** per turn (LLMs can be slow). If an agent doesn't answer in
  time, it counts as **conceding that sub‑game** — or, if you prefer, **one re‑prompt then
  concede**.

### 2.6 Illegal action (usually just a bug)
- **PICK TOGETHER ☐** If an engine submits an illegal action (off‑board, into a barrier, a 6th
  barrier, no action), that sub‑game goes to the other side and you **note it so the bug gets
  fixed**.

### 2.7 Barrier edge cases
- **PICK TOGETHER ☑ (agreed with amireman):** the cop walls **one of its 8 king‑adjacent empty
  cells** — in‑bounds, not the thief's cell, not an existing barrier. The cop **stays on its own
  cell** (placing a barrier is its whole turn); the walled cell is impassable for both from then on.

### 2.8 Move counting
- **PICK TOGETHER ☐** "25 moves" = **25 thief moves**; the thief wins if it finishes its 25th
  move uncaught, and the cop's reply is its last chance to capture.

### 2.9 Observation model (partial observability) — core game logic
- **PICK TOGETHER ☐** An agent always knows **its own** cell; it sees the **opponent** and
  **barriers** only within a **vision radius of 2** (king‑move distance) on the 5×5 board.
  Outside it, no ground truth — only the messages. The referee tool returns just this legal
  view per agent.
- **PICK TOGETHER ☐** Start positions are placed so cop and thief begin **outside each other's
  vision radius** (matches the spec's "initial distance exceeds vision radius").

### 2.10 Capture definition
- **PICK TOGETHER ☐** Capture = cop and thief on the **same cell**, checked after every move
  (cop onto thief, or thief forced onto cop). Swapping cells in one turn (passing through) is
  **not** a capture.

### 2.11 Optional simplifiers — *tick only if BOTH teams want them*
Make the match easier to build and debug.

*Safe for the real series (spec‑compliant):*
- **☐** Wider **vision radius 3** (nearly the whole 5×5) — less reliance on trusting messages.
- **☐** **Fixed start** instead of a seed: cop `[0,0]`, thief `[4,4]`.

*Warm‑up only (smoke test before the graded run — these bend the spec):*
- **☐** 4‑direction movement (no diagonals).
- **☐** Barriers off for one practice sub‑game.
- **☐** Short 15‑move sub‑game.

---

## 3. Making the two systems talk

Practical setup so the cloud match works (and it covers the assignment's "secure URLs / token
auth" requirement at the same time):
- **PICK TOGETHER ☐** **HTTPS only.** Exchange the four MCP URLs out of band (not in this file):
  A‑cop, A‑thief, B‑cop, B‑thief.
- **PICK TOGETHER ☐** Each side gives the other a **token** (sent out of band) used in an
  `Authorization` header; revoke it after the match.
- **PICK TOGETHER ☐** Stay under ~**30 requests/min** per direction so neither side accidentally
  floods the other's API gatekeeper; retry transient errors a few times.
- **PICK TOGETHER ☐** Both sides keep a **full timestamped log** of every message and action —
  for **joint debugging** and as a shared record of how each sub‑game went. Swap logs afterward.

> Note: bluffing inside the `message` is the fun part of the game. Just keep messages
> well‑formed so neither server trips over a bad payload — you don't want to crash your friends'
> system by accident.

---

## 4. Technical hiccups
- **PICK TOGETHER ☐** If a server drops / network glitches mid‑sub‑game, it's a **Technical
  Loss**: void it and **re‑run**, until there are **6 clean sub‑games**. A few retries, then
  pick a new time slot.

---

## 5. One matching report
The spec wants **both teams to email the same JSON** with `"mutual_agreement": true`, and a
mismatch voids the bonus — so just line them up first:
- **PICK TOGETHER ☐** After the 6 clean sub‑games, compare results, agree the per‑sub‑game
  outcomes and totals, **then** each team emails its own copy (identical `sub_games`,
  `totals_by_group`, `bonus_claim`, `mutual_agreement: true`).
- **Bonus scoring (fixed):** higher series total → **10**, other → **7**, exact tie → **5 each**;
  final bonus = **average over all series** (e.g. 10 and 7 → **8.5**). Playing more than one
  team is allowed and encouraged.

### Report JSON shape (spec §9.2) — both teams send this, identical in the agreed fields:
```json
{
  "report_type": "bonus_game",
  "groups": { "group_1": "Team-A", "group_2": "Team-B" },
  "github_repo_group_1": "https://github.com/...",
  "github_repo_group_2": "https://github.com/...",
  "mcp_url_group_1_cop": "https://...",
  "mcp_url_group_1_thief": "https://...",
  "mcp_url_group_2_cop": "https://...",
  "mcp_url_group_2_thief": "https://...",
  "timezone": "Asia/Jerusalem",
  "students_group_1": [],
  "students_group_2": [],
  "sub_games": [],
  "totals_by_group": { "Team-A": 0, "Team-B": 0 },
  "bonus_claim": { "Team-A": 0, "Team-B": 0 },
  "mutual_agreement": true
}
```

---

*Filled in together by both teams — keep a copy in each repo so you're always building against
the same spec.*
