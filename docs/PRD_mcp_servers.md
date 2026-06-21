# PRD — MCP Servers & Orchestrator

**Mechanism PRD** (per submission guidelines §2.3). **Version:** 1.00.
**Parent:** [`PRD.md` §9](PRD.md#9-mcp--orchestration-requirements) · **Design:**
[`PLAN.md` §8–11](PLAN.md#8-mcp-server-design-cop-and-thief).

---

## 1. Description & Theoretical Background

The **Model Context Protocol (MCP)** is an open standard for connecting LLMs to information sources,
tools, and external servers. In this project each agent (Cop, Thief) is fronted by its **own
independent MCP server**. Crucially, the **MCP server does not host the LLM**: it exposes
tools/resources/prompts that wrap the referee's legal view and validate actions. The **orchestrator
(MCP client)** owns the game loop — it calls the LLM provider for the active agent, interprets the
returned tool call/action, and commits it through the agent's MCP server to the referee.

This separation (Server vs Client) is the core architectural point of the assignment (§5.2): the LLM
lives in the client/orchestrator; the MCP servers expose tools only.

---

## 2. Specific Requirements

### 2.1 Two independent servers
- **MUST** run two MCP servers: one Cop, one Thief, preferably **FastMCP**.
- Shared tool implementations parameterized by role (`mcp/tools.py`) → no duplication.
- Dev: separate localhost ports (Cop `:8001`, Thief `:8002`). Cloud: two HTTPS URLs.

### 2.2 Tools exposed (minimum set)

| Tool | Input | Output | Purpose |
|---|---|---|---|
| `get_observation` | `role`, `sub_game`, `move_number` | `Observation` | Legal partial view (fog-of-war) |
| `submit_turn` | `TurnPayload` | `TurnResult` | Commit a validated action |
| `receive_message` | `from_role`, `message` | ack | Deliver opponent's NL message |
| `validate_action` | `role`, `Action` | `{valid, reason}` | Pre-check, no commit |
| `get_match_status` | — | `MatchStatus` | Scores, sub-game, move (orchestrator + GUI) |
| `health_check` | — | `{ok, version}` | Liveness + version probe |

### 2.3 Orchestrator (MCP client)
- Owns the series + sub-game + turn loop (thief first; 6 sub-games; 25 moves).
- Calls the LLM via the gatekeeper; parses the model's `message` + `action`.
- Commits actions via the agent's MCP server; the referee is final authority.
- Handles Technical-Loss (void & rerun) and the heuristic fallback on invalid/unparseable actions.

### 2.4 Development stages (assignment §6)
1. Localhost, two servers on separate ports.
2. Full local pipeline (complete clean series locally).
3. Cloud/public deployment.
4. Secure HTTPS URLs + token authentication (revoke after match).
5. Inter-group match support.

### 2.5 Security
- HTTPS-only public URLs; bearer-token auth in an `Authorization` header (token from env); revoke
  after match. Validate/sanitize all inbound payloads (reject, don't crash).

---

## 3. Input / Output / Performance

| | Spec |
|---|---|
| **Server input** | Schema-validated tool calls (JSON payloads) |
| **Server output** | `Observation` / `TurnResult` / `MatchStatus` / acks (JSON) |
| **Client input** | LLM responses (message + intended tool call) |
| **Client output** | Committed turns, logs, and (series end) a JSON report |
| **Rate** | Stay ~30 requests/min per direction (shared rules §3); gatekeeper enforces |
| **Latency** | Per-turn budget default 30 s (LLMs can be slow); timeout → re-prompt/concede |

### 3.1 Turn sequence (one turn)

```
Orchestrator           Cop/Thief MCP server        Referee (SDK)        LLM provider
    | get_observation(role) -------> |                                       |
    | <----------- Observation ----- | <-- observation_service ----          |
    | -------- llm_decide(role, obs, memory) -------------------------------> |
    | <------------------ message + intended action ------------------------- |
    | submit_turn(TurnPayload) ----> | -- validate+apply --> Referee          |
    | <----------- TurnResult ------- | <----------------------------         |
    | receive_message(other, msg) --> |   (deliver bluffable message)         |
    | log TurnRecord
```

---

## 4. Constraints, Alternatives & Decisions

- **Decision (ADR-001):** FastMCP for both servers — idiomatic MCP, fast localhost→cloud path.
- **Alternative — server hosts the LLM:** **rejected**; violates the Server/Client separation
  (assignment §5.2). The LLM stays in the orchestrator.
- **Alternative — one server for both agents:** rejected; the spec requires **two independent**
  servers (one per agent) so they can be deployed/owned separately (and by different teams in the
  bonus).
- **Constraint:** all URLs/ports/tokens come from config/env (no hard-coding).

---

## 5. Success Criteria & Test Scenarios

**Success:** two servers start independently; all six tools respond per schema; the orchestrator runs
a full autonomous local series; servers never host the LLM.

| # | Scenario | Expected |
|---|---|---|
| T1 | Start Cop + Thief servers on `:8001`/`:8002` | Both `health_check` return `{ok, version:"1.00"}` |
| T2 | `get_observation` for a hidden opponent | Opponent omitted (outside vision radius) |
| T3 | `submit_turn` with a legal action | `accepted`, state advances |
| T4 | `submit_turn` with an illegal action | `rejected` + reason (no crash) |
| T5 | Malformed payload | Schema rejection, server stays up |
| T6 | Full local series via orchestrator | 6 clean sub-games, no manual steps |
| T7 | Injected server crash mid-sub-game | Technical Loss → sub-game rerun |
| T8 | Token missing/invalid (cloud) | 401/handshake failure; valid token succeeds |
| T9 | Contract test per tool | Payload shapes match schemas |
