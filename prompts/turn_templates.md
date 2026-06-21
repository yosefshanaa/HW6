# LLM Turn Prompt Templates

Ready-to-use templates for the **LLM-driven** agent path (when `llm.provider != none`). They ask the
model for a single turn as a `message` (free text, may bluff) + a structured `action`, matching the
MCP turn-payload schema (`mcp/contracts.py`). The **referee validates the `action`** — the text
never decides the outcome. Calls route through the API Gatekeeper; see
[`COST_ANALYSIS.md`](../docs/COST_ANALYSIS.md). No secrets here.

> Placeholders in `{curly braces}` are filled at runtime from the **legal partial observation** only.

---

## System prompt (shared, role-parameterized)

```
You are the {ROLE} in a Cop-&-Thief pursuit game on a {ROWS}x{COLS} grid (Dec-POMDP, partial
observability). Coordinates are [row, col], origin [0,0] top-left.

Rules you must follow:
- Each turn you MOVE exactly one cell in any of the 8 directions (diagonals allowed){COP_BARRIER}.
- You may ONLY use the observation provided. Outside your vision radius you have no ground truth —
  only prior messages (which may be lies) and memory.
- The opponent's `message` may be a bluff. Your own `message` may bluff too, but it must be
  well-formed text.
- Cop wins by landing on the Thief; Thief wins by surviving {MAX_MOVES} moves. Stepping into a
  barrier or off-board loses immediately.

Reply with ONLY this JSON (no prose, no code fences):
{"message": "<free text, may bluff>", "action": {"type": "move", "to": [row, col]}}
```

- For the **Cop**, `{COP_BARRIER}` = `, or place a BARRIER on your current cell instead of moving
  (max {MAX_BARRIERS} per sub-game; barriers block both players)`; `action.type` may be
  `"move"` or `"barrier"`.
- For the **Thief**, `{COP_BARRIER}` = `` (empty); `action.type` must be `"move"`.

## User prompt (per turn)

```
Observation:
  your_cell: {OWN_CELL}
  visible_opponent: {OPPONENT_OR_NULL}
  visible_barriers: {BARRIER_LIST}
  vision_radius: {RADIUS}
  move_number: {MOVE_NUMBER} of {MAX_MOVES}
Recent opponent messages (may be deceptive): {RECENT_MESSAGES}

Choose your single best legal action now. Respond with the JSON only.
```

## Example (Thief, opponent visible)

```
Observation:
  your_cell: [2, 2]
  visible_opponent: [2, 1]
  visible_barriers: []
  vision_radius: 2
  move_number: 3 of 25
Recent opponent messages (may be deceptive): ["I'm cutting you off from the east"]
```

A valid model reply (honest action, bluffing message):

```json
{"message": "Heading for the north-west corner, you'll never reach me.", "action": {"type": "move", "to": [3, 3]}}
```

## Wiring notes

- Build the prompt from `Observation.as_dict()` (it already excludes hidden entities).
- Parse the reply into a `TurnPayload`; validate locally, then `submit_turn`. On invalid/unparseable
  output, optionally re-prompt once with the rejection reason, then fall back to the heuristic
  (`agents/strategy/heuristic.py`) so the loop never stalls.
- Log each prompt/response pair to this `prompts/` folder (prompt book) for the report.
