# PLAN — HW6: Dual AI Agent Race via MCP Servers (Cop & Thief)

**Document:** Architecture & Planning (`docs/PLAN.md`)
**Version:** 1.00
**Status:** Draft for approval (pre-implementation)
**Companion docs:** [`PRD.md`](PRD.md) (requirements), [`TODO.md`](TODO.md) (execution checklist),
per-mechanism PRDs (`PRD_*.md`).
**Last updated:** 2026-06-21

> This document defines *how* we build what `PRD.md` requires: the architecture (C4 text views),
> the project tree, the SDK boundary, the domain model, component designs, the orchestrator loop,
> deployment, testing, security, error handling, milestones, and Architectural Decision Records.

---

## 1. Technical Architecture

The system has three runtime tiers and one shared library:

1. **Orchestrator / MCP client (the brain).** Owns the game loop, calls the LLM provider for the
   active agent, interprets the agent's intended action, and commits it through the agent's MCP
   server to the referee. Hosts the API Gatekeeper, the config loader, logging, and the reporting
   component.
2. **Two MCP servers (Cop, Thief).** Independent FastMCP services exposing tools/resources/prompts.
   They wrap the **referee/game engine** view for their agent and validate actions. They **do not**
   host the LLM.
3. **Referee / game engine (single source of truth).** Holds authoritative state, enforces rules,
   computes partial observations, and scores sub-games. In the internal game one referee serves both
   agents; in the bonus game the Cop-side engine is referee for its sub-games (ADR-004).
4. **Shared library / SDK.** The single entry point all consumers (CLI, GUI, reporting, peer
   integration) call. Contains domain models, services, gatekeeper, config, version, logging.

```
            +-------------------- Orchestrator (MCP client) --------------------+
            |  game loop · LLM calls · gatekeeper · config · logging · report   |
            +----+-------------------------+-----------------------------+------+
                 | LLM API (cloud/Ollama)  | MCP (HTTP/HTTPS)            | Gmail API
                 v                         v                            v
           +-----------+        +----------+-----------+         +------------+
           |  LLM      |        | Cop MCP  | Thief MCP  |         |  Gmail     |
           | provider  |        | server   | server     |         |  (report)  |
           +-----------+        +----+-----+-----+------+         +------------+
                                     |           |
                                     v           v
                              +--------------------------+
                              | Referee / Game Engine    |  <-- single source of truth
                              | state · rules · scoring  |
                              +--------------------------+
```

---

## 2. C4-Style Architecture (text form)

### 2.1 Context (Level 1)

- **Actors:** *Operator* (teammate who launches a run), *Instructor* (receives the JSON email),
  *Partner team* (bonus match), *Automated grader/parser*.
- **System:** *Cop & Thief MCP Pipeline*.
- **External systems:** *LLM provider* (OpenAI/Anthropic/Gemini or local Ollama), *Gmail API*,
  *Partner team's MCP servers* (bonus), *Cloud host* (e.g., Prefect Cloud).
- **Primary flows:** Operator → run series → pipeline plays 6 clean sub-games → emails JSON to
  instructor; (bonus) pipeline ↔ partner MCP servers.

### 2.2 Containers (Level 2)

| Container | Responsibility | Tech |
|---|---|---|
| **Orchestrator CLI/app** | Game loop, LLM calls, gatekeeper, reporting, config, logging | Python, `uv` |
| **Cop MCP server** | Cop tools/resources/prompts; validates Cop actions | FastMCP |
| **Thief MCP server** | Thief tools/resources/prompts; validates Thief actions | FastMCP |
| **Referee/Engine (library)** | Authoritative state, rules, observations, scoring | Python (in SDK) |
| **GUI** | Visualize board/observations/messages/scores/logs | Python GUI (calls SDK) |
| **Reporting** | Build + send JSON report | Gmail API client (via gatekeeper) |
| **Config store** | `config.yaml` + `rate_limits.json` + `.env` | Files / env |

### 2.3 Components (Level 3) — within the orchestrator/SDK

- `SDK` facade — single entry point.
- `GameEngine` / `Referee` — state machine + rule enforcement.
- `ObservationService` — computes per-agent partial views.
- `Orchestrator` — turn loop, sub-game/series control, Technical-Loss handling.
- `AgentClient` — talks to one MCP server (Cop or Thief).
- `LlmClient` — provider-agnostic LLM calls (via gatekeeper).
- `ApiGatekeeper` — rate limits, queue, retries, logging, monitoring.
- `StrategyEngine` — baseline heuristic / optional Q-table (server-side helper).
- `ReportBuilder` + `GmailReporter` — assemble + send JSON report.
- `ConfigManager`, `Version`, `Logger`, `ReplayStore`.

### 2.4 Key Code / Package Modules (Level 4)

See the project tree (§3). Each Level-3 component maps to one module/package under
`src/cop_thief/`, behind `sdk/sdk.py`.

---

## 3. Proposed Project Tree

> Aligned to the submission guidelines §2.4. Package name: **`cop_thief`**. Files ≤150 code lines.

```
HW6/
├── src/
│   └── cop_thief/
│       ├── __init__.py            # exports public API + __version__
│       ├── main.py                # CLI entry: run a series
│       ├── constants.py           # immutable enums/constants (no config values)
│       ├── sdk/
│       │   └── sdk.py             # SINGLE entry point for all logic
│       ├── domain/                # domain models (dataclasses/enums)
│       │   ├── position.py
│       │   ├── action.py
│       │   ├── barrier.py
│       │   ├── observation.py
│       │   ├── game_state.py
│       │   ├── records.py         # TurnRecord, SubGameResult, MatchReport
│       │   └── roles.py           # PlayerRole enum
│       ├── engine/                # referee / game engine
│       │   ├── referee.py
│       │   ├── rules.py
│       │   ├── movement.py
│       │   ├── scoring.py
│       │   └── observation_service.py
│       ├── orchestrator/
│       │   ├── orchestrator.py    # series + sub-game loop
│       │   ├── turn_loop.py       # one turn
│       │   └── technical_loss.py  # void & rerun policy
│       ├── agents/
│       │   ├── agent_client.py    # MCP client wrapper
│       │   ├── llm_client.py      # provider-agnostic LLM calls
│       │   └── strategy/
│       │       ├── base.py        # Strategy base class
│       │       ├── heuristic.py   # baseline
│       │       └── q_table.py     # optional tabular Q-learning
│       ├── mcp/
│       │   ├── cop_server.py      # FastMCP app (Cop)
│       │   ├── thief_server.py    # FastMCP app (Thief)
│       │   └── tools.py           # shared tool implementations
│       ├── reporting/
│       │   ├── report_builder.py
│       │   ├── gmail_reporter.py
│       │   └── schemas.py         # JSON schemas (internal + bonus)
│       ├── gui/
│       │   └── app.py             # GUI (calls SDK; omitted from coverage)
│       └── shared/
│           ├── gatekeeper.py      # API Gatekeeper
│           ├── config.py          # ConfigManager + validation
│           ├── version.py         # __version__ = "1.00"
│           ├── logging_setup.py
│           └── replay.py          # log + replay store
├── tests/
│   ├── unit/                      # mirrors src/ structure
│   ├── integration/               # full sub-game, MCP contract, report
│   └── conftest.py                # shared fixtures + mocks
├── docs/
│   ├── PRD.md  PLAN.md  TODO.md
│   └── PRD_game_engine.md  PRD_mcp_servers.md  PRD_agent_strategy.md
│       PRD_partial_observability.md  PRD_gmail_reporting.md
│       PRD_bonus_match.md  PRD_gui_and_logs.md
├── config/
│   ├── config.yaml                # main game/system config (versioned)
│   ├── rate_limits.json           # gatekeeper limits (version "1.00")
│   └── logging_config.json
├── data/                          # seeds / fixtures
├── results/                       # series results, charts, screenshots
├── assets/                        # GUI assets, diagrams
├── notebooks/                     # analysis notebooks
├── prompts/                       # prompt book / prompt log
├── README.md                      # user manual (MANDATORY)
├── pyproject.toml                 # build, deps, ruff, coverage
├── uv.lock                        # committed
├── .env-example                   # dummy secret placeholders
└── .gitignore                     # already lists secret patterns
```

---

## 4. SDK Boundary

Per guidelines §4.1: **every business operation is reachable only through `sdk/sdk.py`.** GUI, CLI,
reporting, and any external/peer integration call the SDK — never internal services or the engine
directly.

```
External consumers (CLI · GUI · Reporting · Peer/bonus)
                         |
                         v
                +-----------------+
                |      SDK        |  single entry point for ALL logic
                +--------+--------+
                         |
                         v
        Domain services (Orchestrator · Engine · Agents · Reporting)
                         |
                         v
        Infrastructure (LLM API · MCP transport · Gmail · file I/O)
```

Representative SDK surface (illustrative signatures):

```python
class CopThiefSDK:
    def run_series(self, config_path: str | None = None) -> MatchReport: ...
    def run_sub_game(self, sub_game_index: int) -> SubGameResult: ...
    def get_observation(self, role: PlayerRole) -> Observation: ...
    def submit_turn(self, role: PlayerRole, turn: TurnPayload) -> TurnResult: ...
    def build_report(self, report_type: str = "internal") -> dict: ...
    def send_report(self, report: dict) -> str: ...   # returns message id
    def get_match_status(self) -> MatchStatus: ...
```

No GUI/CLI module contains business logic; they translate user intent into SDK calls and render
results.

---

## 5. Domain Model

Plain, testable dataclasses/enums (no I/O), defined under `src/cop_thief/domain/`.

| Type | Fields (essential) | Notes |
|---|---|---|
| **`Position`** | `row: int`, `col: int` | `[row, col]`, origin top-left; helpers: `chebyshev(other)`, `neighbors8()`, `in_bounds(grid)` |
| **`PlayerRole`** | enum `COP` / `THIEF` | drives turn order & capabilities |
| **`Action`** | `type: {MOVE, BARRIER}`, `to: Position` | `BARRIER` only valid for Cop |
| **`Barrier`** | `cell: Position`, `placed_by: PlayerRole`, `move_number: int` | impassable to both |
| **`Observation`** | `role`, `own_cell`, `visible_opponent: Position\|None`, `visible_barriers: list[Position]`, `vision_radius`, `move_number` | the legal partial view |
| **`TurnPayload`** | `sub_game`, `move_number`, `role`, `message: str`, `action: Action` | the wire envelope (shared rules §2.2) |
| **`GameState`** | `grid_size`, `cop: Position`, `thief: Position`, `barriers: list[Barrier]`, `move_number`, `turn: PlayerRole`, `status` | authoritative state |
| **`TurnRecord`** | `timestamp`, `sub_game`, `move_number`, `role`, `observation`, `message`, `action`, `validation`, `resulting_state` | one log/replay row |
| **`SubGameResult`** | `index`, `winner: PlayerRole`, `moves_played`, `cop_score`, `thief_score`, `technical_loss: bool`, `turns: list[TurnRecord]` | per sub-game |
| **`MatchReport`** | `report_type`, `sub_games: list[SubGameResult]`, `totals`, metadata (team, repo, urls, timezone) | maps to §9.1/§9.2 JSON |

Turn payload (canonical JSON) — shared rules §2.2:

```json
{
  "sub_game": 1,
  "move_number": 7,
  "role": "thief",
  "message": "free natural-language text, may bluff",
  "action": { "type": "move|barrier", "to": [row, col] }
}
```

---

## 6. Game Engine Design

- **`GameState`** is the only authoritative state. All mutations go through `Referee`.
- **`rules.py`** validates an `Action` against the current state: in bounds; exactly one king-move
  step for `MOVE`; target not a barrier; `BARRIER` only for Cop, on the Cop's own cell, ≤5 total,
  not on the Thief's cell or an existing barrier.
- **`movement.py`** enumerates the 8 king-moves and applies a validated move.
- **`scoring.py`** maps a sub-game outcome to the scoring table (config-driven values).
- **Capture check** runs after each applied move (same-cell occupancy; swap is not capture).
- **Move counting:** the sub-game ends after the 25th **Thief** move + the Cop's reply, or earlier on
  capture / illegal action.
- Engine is **pure** (no network/LLM) → fully unit-testable and deterministic given a seed.

Detailed state machine and edge cases: [`PRD_game_engine.md`](PRD_game_engine.md).

---

## 7. Referee / State Authority Design

- A single **`Referee`** instance owns `GameState` for a sub-game and is the **only** writer.
- MCP servers ask the referee (via the SDK) for observations and submit actions for validation; they
  never mutate state themselves.
- **Internal game:** one referee for both agents.
- **Bonus game:** the **Cop-side engine is referee** for sub-games where that team is Cop; the other
  side **mirrors and flags** any mismatch (ADR-004; shared rules §2.1).
- Every accepted/rejected action is recorded as a `TurnRecord` (auditability).

---

## 8. MCP Server Design (Cop and Thief)

- Two independent FastMCP apps (`cop_server.py`, `thief_server.py`) sharing tool implementations
  (`tools.py`) parameterized by role → no duplication (guidelines §4.2).
- Each server is **stateless about strategy**: it exposes the referee's legal view for its agent and
  validates/commits actions. The LLM lives in the orchestrator, not the server.
- Transport: localhost ports in dev (e.g., Cop `:8001`, Thief `:8002`); HTTPS public URLs + token
  auth in cloud.
- Auth: bearer token in an `Authorization` header, validated by middleware; token from env; revoke
  after match.

Full server contract & sequence: [`PRD_mcp_servers.md`](PRD_mcp_servers.md).

---

## 9. MCP Tools to Expose

| Tool | Input | Output | Purpose |
|---|---|---|---|
| `get_observation` | `role`, `sub_game`, `move_number` | `Observation` (legal partial view) | What the agent may see |
| `submit_turn` | `TurnPayload` | `TurnResult` (accepted/rejected, new status) | Commit a validated action |
| `receive_message` | `from_role`, `message` | ack | Deliver opponent's NL message |
| `validate_action` | `role`, `Action` | `{valid: bool, reason}` | Pre-check without committing |
| `get_match_status` | — | `MatchStatus` (scores, sub-game, move) | Progress/health for orchestrator + GUI |
| `health_check` | — | `{ok: true, version}` | Liveness + version probe |

All tool payloads are schema-validated; contract tests assert the shapes (see §19).

---

## 10. Orchestrator Flow

```
for sub_game in 1..num_games:                  # default 6
    state = referee.new_sub_game(seed, start_mode)   # cop & thief outside vision radius
    while not state.terminal and moves < max_moves:  # 25
        for role in [THIEF, COP]:              # thief first
            obs   = get_observation(role)
            reply = llm_decide(role, obs, memory)      # via gatekeeper
            turn  = parse(reply)                        # message + action
            res   = submit_turn(role, turn)             # referee validates/commits
            deliver_message(other(role), turn.message)
            log(TurnRecord)
            if res.capture or res.illegal: break
        if technical_failure(): mark_technical_loss(); break
    if technical_loss: rerun sub_game            # don't count it
    else: results.append(SubGameResult)
report = build_report(results); send_report(report)   # Gmail, JSON-only
```

Technical-Loss handling: any server crash / network glitch / LLM hard error mid-sub-game voids that
sub-game and reruns it until there are exactly 6 clean sub-games (FR-22).

---

## 11. LLM Prompt / Tool-Call Loop

1. Build a prompt from: role, the **legal observation only**, recent messages, memory, and the rules
   summary. Prompts are versioned in `prompts/` (prompt book).
2. Call the LLM (via `LlmClient` → gatekeeper). The model returns an intended **tool call / action**
   plus a natural-language `message`.
3. Parse into a `TurnPayload`. Validate locally, then `submit_turn` to the MCP server (referee is the
   final authority — the model's text never decides the outcome).
4. On invalid action: optionally one re-prompt with the rejection reason, then fall back to the
   baseline heuristic (so the loop never stalls).
5. Record tokens for the cost analysis.

---

## 12. Agent Strategy Design

- **Baseline heuristic (required path):** Cop minimizes Chebyshev distance to the last known/most
  likely Thief cell and places barriers to cut off escape; Thief maximizes distance and avoids
  barriers/edges. Works on partial info + (possibly false) messages.
- **Optional tabular Q-Learning (assignment §8):** state = discretized positions; actions = 8 moves
  (+ barrier for Cop); reward shaping (small step penalty, capture reward, illegal/edge penalty);
  Bellman update. No neural nets.
- **Deception / bluff handling:** the `message` may be false; strategy weights messages by a
  trust/recency factor and never treats a message as ground truth. Within-radius observations
  override messages.

Details, reward table, and the Q-update: [`PRD_agent_strategy.md`](PRD_agent_strategy.md).

---

## 13. Gmail Reporting Flow

```
results -> ReportBuilder.build(report_type) -> dict (schema-validated)
        -> json.dumps(report)                -> body (JSON ONLY)
        -> GmailReporter.send(to=recipient, body)  # via gatekeeper, Gmail API
```

- OAuth: `credentials.json` + `token.json` (never committed); Desktop app; External audience + Test
  user; least-privilege scope (see [`PRD_gmail_reporting.md`](PRD_gmail_reporting.md)).
- The email **body is only the JSON** (no subject text leakage into the body, no signatures).
- Sending is idempotent per series (one report) and goes through the gatekeeper for retries.

---

## 14. Config Loading and Validation

- `ConfigManager` loads `config/config.yaml` (game/system) and `config/rate_limits.json` (gatekeeper)
  and overlays environment variables for secrets.
- **Validation at startup:** schema check (types/ranges), required keys present, and a **version
  compatibility check** (`config.version`, `rate_limits.version` start at `1.00`).
- Access pattern is `cfg.get("grid_size", default)` — no literal game values in code (guidelines
  §7.2). Constants in `constants.py` are immutable, non-configurable enums only.

---

## 15. API Gatekeeper Design

Per guidelines §5 — **every** external API call (LLM, Gmail, peer MCP) goes through it.

```python
class ApiGatekeeper:
    """Centralized API call manager: rate limits, queue, retries, logging, monitoring."""
    def __init__(self, config: RateLimitConfig): ...
    def execute(self, api_call, *args, **kwargs):
        # check rate limits -> queue if limited (FIFO, max depth, backpressure)
        # retry transient failures (max_retries, retry_after_seconds)
        # log every call; expose metrics
        ...
    def get_queue_status(self) -> QueueStatus: ...
```

Config (`rate_limits.json`, version `"1.00"`): `requests_per_minute: 30`, `requests_per_hour: 500`,
`concurrent_max: 5`, `retry_after_seconds: 30`, `max_retries: 3`. Stay ~30 req/min per direction
(shared rules §3).

---

## 16. Logging and Replay Design

- Structured logging via `logging_setup.py` (config in `logging_config.json`).
- `ReplayStore` persists one `TurnRecord` per turn (timestamp, sub-game, move number, role,
  observation, message, action, validation, resulting state) to `results/` as JSONL.
- A replay loads a series JSONL and re-renders it in the GUI/CLI for debugging and for swapping logs
  with the partner team after the bonus match.

Details: [`PRD_gui_and_logs.md`](PRD_gui_and_logs.md).

---

## 17. GUI Design

- A board view (grid, Cop, Thief, barriers), a turn indicator, per-agent observation (fog-of-war)
  panels, a message log, a score panel, and a scrollable event log.
- Calls the SDK only; reads `MatchStatus` + `TurnRecord`s.
- Follows Nielsen heuristics; screenshots captured into `assets/`/`results/` for the report.
- A rich-CLI fallback renders the same information if no GUI toolkit is available.

---

## 18. Deployment Plan

| Stage | Target | Notes |
|---|---|---|
| **Local** | Two MCP servers on localhost ports (`:8001`, `:8002`) + orchestrator | Stage 1–2 (assignment §6) |
| **Cloud** | MCP servers to public host (e.g., Prefect Cloud or equivalent) | Stage 3 |
| **Public HTTPS** | HTTPS-only URLs; outbound from orchestrator | Stage 4 |
| **Token auth** | Bearer token in `Authorization` header; revoke after match | Stage 4 |
| **Inter-group** | Exchange 4 URLs + tokens out-of-band; rate-limit handshake | Stage 5 (bonus) |

LLM hosting options (ADR-002): cloud API (recommended); local Ollama only loopback or tunneled with
auth+HTTPS (ngrok Traffic Policy / Localtonet / Nginx reverse proxy + Certbot + htpasswd + firewall);
hybrid (local orchestrator+LLM, cloud MCP). **Never** expose Ollama directly.

---

## 19. Testing Plan

| Layer | What | Tooling |
|---|---|---|
| **Unit** | Engine rules, movement, scoring, observation, domain models, config, gatekeeper, report builder | `pytest`, mirrors `src/` |
| **Integration** | Full sub-game simulation (engine + agents stubbed), orchestrator loop, Technical-Loss rerun | `pytest` |
| **Contract** | MCP tool payloads (`get_observation`, `submit_turn`, …) match schemas | `pytest` + JSON schema |
| **Simulation** | Deterministic seeded series → expected scores/winners | `pytest` |
| **Report schema** | Internal (§9.1) and bonus (§9.2) JSON validate against schema; body is JSON-only | `pytest` + `jsonschema` |
| **Gmail (mocked)** | Report send path with the Gmail client fully mocked | `pytest` + mocks |

Rules: TDD (red-green-refactor); ≥85% coverage (`fail_under = 85`); mock all external services (no
test hits a real LLM/Gmail/peer); test files ≤150 lines; every public function tested for happy path
and errors.

---

## 20. Security Plan

- HTTPS-only public MCP URLs; bearer-token auth via middleware; revoke after match.
- Secrets only via env/`.env`; `.env-example` committed; `.gitignore` lists `.env`,
  `credentials.json`, `token.json`, `*.pem`, `*.key`.
- Least-privilege Gmail scope; document why Calendar scope is **not** needed for this project.
- Validate/sanitize all inbound MCP payloads (reject, don't crash) to resist malformed/abusive input;
  treat the bonus `message` as untrusted but well-formed.
- Periodic token rotation; usage monitoring through the gatekeeper.

---

## 21. Error Handling Plan

- **Defensive validation** at every boundary (config, MCP payloads, LLM output, Gmail responses).
- **Transient errors** (network, 429, 5xx) → gatekeeper retries with backoff.
- **Hard errors mid-sub-game** → Technical Loss → void & rerun.
- **Invalid agent action** → optional single re-prompt → fall back to heuristic (loop never stalls).
- **Graceful degradation:** GUI failure does not stop the headless series; logging always continues.
- Clear, specific error messages + structured logs for every failure (guidelines §6.3).

---

## 22. Milestones and Implementation Phases

Aligned to `TODO.md` phases and the assignment's recommended order (§13).

| Milestone | Phases (see TODO) | Definition of done |
|---|---|---|
| **M0 Docs & scaffold** | 0–2 | Docs approved; `uv` project, config/version/secrets in place |
| **M1 Core game** | 3–5 | Engine + observation + baseline strategy; seeded sub-game tests green |
| **M2 MCP local** | 6–7 | Two servers on localhost; orchestrator plays a full local series |
| **M3 NL + logging + report model** | 8–10 | Message protocol; full logs/replay; Gmail JSON report (mocked + live) |
| **M4 GUI** | 11 | GUI visualizes board/observations/messages/scores/logs |
| **M5 Cloud + bonus** | 12, 15 | HTTPS + token auth; interoperability with partner; matching JSON |
| **M6 Quality & submission** | 13–14, 16–17 | ≥85% coverage, Ruff clean; README; research report; final checklist |

---

## 23. Architectural Decision Records (ADRs)

> Format: Context → Decision → Consequences. These are the initial ADRs; add more as the design
> evolves (one ADR per significant decision).

### ADR-001 — Use FastMCP for the two MCP servers
- **Context:** Need two independent MCP servers exposing tools/resources/prompts without hosting the
  LLM (assignment §5). FastMCP is explicitly recommended.
- **Decision:** Implement Cop and Thief servers with **FastMCP**, sharing role-parameterized tool
  implementations.
- **Consequences:** Fast to build, idiomatic MCP, easy localhost→cloud path; tied to FastMCP's API;
  shared `tools.py` avoids duplication.

### ADR-002 — Cloud LLM API as default; Ollama only secured
- **Context:** Three LLM access patterns (cloud API / exposed-local Ollama / hybrid). Security and
  simplicity matter; Ollama must never be exposed without HTTPS+auth.
- **Decision:** Default to a **cloud LLM API** (OpenAI/Anthropic/Gemini); allow local Ollama **only**
  loopback or securely tunneled; allow hybrid (local orchestrator, cloud MCP).
- **Consequences:** Simple, reliable, low-latency default; provider cost (tracked in cost analysis);
  `LlmClient` is provider-agnostic so we can switch via config.

### ADR-003 — Structured `action` + natural-language `message`
- **Context:** Agents talk in free NL (bluffing is part of the game) but the outcome must be
  unambiguous and validated.
- **Decision:** Every turn carries both a free `message` and a structured `action`; the **referee
  decides on the `action`, never the text** (shared rules §2.2).
- **Consequences:** Bluffing preserved; deterministic adjudication; strict payload schema needed
  (contract tests).

### ADR-004 — Central referee authority for state
- **Context:** Two engines must never disagree about positions/rules.
- **Decision:** A **single referee** owns authoritative state. Internal game: one referee. Bonus:
  the **Cop-side engine is referee** for its sub-games; the other side mirrors and flags mismatches.
- **Consequences:** No silent divergence; clear ownership; the mirroring side must implement
  mismatch detection (and we log everything for joint debugging).

### ADR-005 — Gmail API for JSON-only reporting
- **Context:** Report must be emailed automatically as **JSON only** to a fixed address; reliability
  and least privilege matter.
- **Decision:** Use the **Gmail API** with OAuth (Desktop app, External + Test user), minimal scope,
  `credentials.json`/`token.json` never committed; body = JSON only.
- **Consequences:** Reliable, auditable sending; one-time OAuth consent setup; scope documented as
  least-privilege (Calendar not needed for this project).

### ADR-006 — Config-first design (no hard-coding)
- **Context:** Assignment §10 + guidelines §7.2 forbid hard-coded configurable values.
- **Decision:** All tunables in `config.yaml`/`rate_limits.json`; secrets in env/`.env`; constants
  module holds only non-configurable enums; startup validation + version checks.
- **Consequences:** Easy experiments (grid size, vision radius, model) without code changes;
  validation code required; clean separation of secrets/config/constants.

### ADR-007 — SDK boundary + API Gatekeeper
- **Context:** Guidelines mandate an SDK layer and that all external calls go through a gatekeeper.
- **Decision:** All consumers call `sdk/sdk.py`; all external calls (LLM/Gmail/peer MCP) go through
  `ApiGatekeeper`.
- **Consequences:** Centralized rate limiting/retries/logging; testable seams (mock at SDK and
  gatekeeper); slight indirection overhead.
