# PRD — HW6: Dual AI Agent Race via MCP Servers (Cop & Thief)

**Document:** Product Requirements Document (`docs/PRD.md`)
**Project:** Cop & Thief — a partially observable, dual-agent pursuit game played autonomously by two
AI agents through independent MCP servers.
**Version:** 1.00
**Status:** Draft for approval (pre-implementation)
**Owner:** `TODO: <team lead / product owner>`
**Last updated:** 2026-06-21

> This is the central requirements document. It defines *what* the system must do and *why*.
> The *how* (architecture, modules, ADRs) lives in [`PLAN.md`](PLAN.md); the execution checklist
> lives in [`TODO.md`](TODO.md). Major mechanisms have dedicated PRDs — see
> [§22 Supporting PRDs](#22-supporting-prds).

---

## 1. Title and Project Overview

**Cop & Thief** is a fully autonomous pipeline in which two AI agents — a **Cop** and a **Thief** —
play a turn-based pursuit game on a grid. Each agent is driven by an LLM and exposes its
capabilities through its **own independent MCP (Model Context Protocol) server**. An orchestrator
(the MCP *client*) drives the match: it queries each agent for a turn, lets the agent reason over a
**partial observation**, and commits the agent's structured action to an authoritative game engine
(the referee). Agents also exchange **free natural-language messages** that may contain bluffs and
deception.

The deliverable is graded primarily on **orchestration, systems engineering, MCP integration,
communication, reporting, and reliable automation** — *not* on which agent wins or on the
sophistication of the game strategy. At the end of a clean series of 6 sub-games, the system emails
a **JSON-only report** to the course mailbox via the Gmail API.

The project also targets an optional **inter-group bonus match** in which two friendly teams connect
their cloud-hosted MCP servers and play a cross-team series (see
[`PRD_bonus_match.md`](PRD_bonus_match.md)).

### 1.1 Elevator summary

| Aspect | Summary |
|---|---|
| Domain | Multi-agent pursuit / evasion (Cop chases Thief) on a configurable grid |
| Decision model | Decentralized Partially Observable Markov Decision Process (Dec-POMDP) |
| Agents | 2 — Cop and Thief, each behind its own MCP server |
| LLM hosting | MCP servers do **not** host the LLM; the orchestrator calls the LLM API |
| Comms | Free natural language (`message`) + authoritative structured `action` |
| Output | One JSON-only email report per clean 6-sub-game series |
| Grade focus | Orchestration & system engineering, not game outcome |

---

## 2. Source Documents Consulted

This PRD is derived **directly** from the following sources. Where a requirement is quoted, the
source is noted inline.

1. **`ex06-Dual AI agent race via MCP servers.pdf`** — Dr. Yoram Segal, L09 v1.0 (2026-06-19). The
   authoritative assignment spec: game rules (§4), MCP architecture (§5–7), Q-Learning (§8), JSON
   report schemas (§9.1/§9.2), config file (§10), README/scientific report (§11), GUI & bonus
   (§12), recommended development order (§13).
2. **`software_submission_guidelines-V3.pdf`** — Dr. Yoram Segal, v3.00 (2026-03-26). How the code
   must be built and submitted: mandatory `README.md` + `docs/` (PRD/PLAN/TODO + per-mechanism
   PRDs), SDK layer, OOP/no-duplication, files ≤150 code lines, API Gatekeeper, config-first / no
   hard-coding, `.env-example`, Ruff zero violations, TDD ≥85% coverage, `uv`-only, version starting
   at 1.00, cost analysis, research plan, ISO/IEC 25010.
3. **`main-google-api-installtion-guid.pdf`** (and its identical duplicate `… (1).pdf`) — Dr. Yoram
   Segal, May 2026. Step-by-step Gmail/Calendar OAuth setup: enable Gmail API (Calendar optional),
   OAuth Client ID (Desktop app), External audience + Test users, scopes
   `gmail.modify` and `calendar`, producing `credentials.json` + `token.json`.
4. **`SHARED_MATCH_RULES.md`** (repo root) — the co-written shared spec both friendly teams build
   against for the bonus match (coordinate convention, turn payload, vision model, referee
   authority, HTTPS + token handshake, technical-loss handling, matching JSON report).

> The two Google API guide PDFs are byte-identical duplicates and are treated as a **single** Gmail
> OAuth source.

---

## 3. Problem Statement

Building a single autonomous agent that acts in a static environment is well understood. This
project raises the bar: students must **orchestrate two independent autonomous agents** that operate
in a **decentralized, partially observable, real-time** setting and must coordinate over a network,
each behind its own MCP server, while communicating in natural language that may be deceptive.

The hard problems are therefore **not** "win the game". They are:

- **Reliable orchestration** of a turn loop across two networked MCP servers and an LLM provider,
  with retries, rate limiting, and clean recovery from transient failures.
- **Protocol & contract discipline** — every turn must carry a well-formed `message` + `action`
  envelope that a referee can validate unambiguously, even across two independently developed
  engines (bonus match).
- **Partial observability** — agents only see within a vision radius and must reason about an
  opponent they cannot directly observe, relying on messages they cannot fully trust.
- **Auditability & reporting** — every message and action is timestamped and logged; the final
  result is delivered as a machine-parseable JSON-only email.
- **Engineering quality** — the codebase must meet the software submission guidelines (SDK layer,
  gatekeeper, TDD ≥85%, Ruff-clean, `uv`-only, no hard-coding).

---

## 4. Goals and Non-Goals

### 4.1 Goals (in priority order)

| # | Goal | Why it matters |
|---|---|---|
| G1 | A complete, autonomous end-to-end pipeline that plays a full 6-sub-game series with **zero manual intervention** from start to email report | Primary grade criterion (assignment §3, §14) |
| G2 | Two independent MCP servers (one Cop, one Thief), preferring FastMCP, exposing tools/resources/prompts but **not** hosting the LLM | Assignment §5 |
| G3 | A central, authoritative referee/game engine enforcing all rules and partial observability | Assignment §4; shared rules §2.1 |
| G4 | Correct, well-formed natural-language + structured-action turn protocol | Shared rules §2.2; assignment §5 |
| G5 | JSON-only automated email report via Gmail API at series end | Assignment §9 |
| G6 | Full software-quality compliance (SDK, gatekeeper, TDD ≥85%, Ruff, `uv`, config-first) | Submission guidelines |
| G7 | Config-driven, no hard-coded game parameters | Assignment §10; guidelines §7.2 |
| G8 | Complete timestamped logs + replay for every message and action | Assignment §11; shared rules §3 |
| G9 | Cloud deployment with HTTPS + token auth, enabling the inter-group bonus match | Assignment §6, §12 |
| G10 | GUI visualizing board, agents, barriers, turns, observations, messages, scores, logs | Assignment §12; guidelines §10 |

### 4.2 Non-Goals

- **Not** optimizing for win rate or building a state-of-the-art game AI. A baseline heuristic is
  sufficient; Q-Learning is **recommended, not required** (assignment §8).
- **Not** training deep neural networks. If RL is used, tabular Q-Learning suffices (assignment §8).
- **Not** building a general game platform; the scope is Cop & Thief with a configurable grid.
- **Not** exposing Ollama (or any LLM) publicly without HTTPS + auth (assignment §7.2).
- **Not** human-vs-agent play. Both agents are autonomous; humans only observe.

---

## 5. Stakeholders / Users

| Stakeholder | Interest |
|---|---|
| **Course instructor (Dr. Yoram Segal)** | Grades orchestration, engineering quality, reporting; receives the JSON email report at `rmisegal+uoh26b@gmail.com` |
| **Our team (developers)** | Build, test, deploy, and operate the pipeline |
| **The friendly partner team** | Interoperates for the bonus match via the shared spec |
| **Operator (a teammate at run time)** | Starts a series, monitors logs/GUI, confirms 6 clean sub-games |
| **Automated graders / parsers** | Consume the JSON-only report email and the GitHub repo |

### 5.1 Primary user stories

- *As an operator*, I run one command and the system plays a full clean 6-sub-game series and emails
  the JSON report, with no further input.
- *As an operator*, when a sub-game suffers a technical failure, the system voids it and reruns until
  there are 6 clean sub-games.
- *As a developer*, I change `grid_size`, `vision_radius`, or the LLM model in config and the system
  adapts without code changes.
- *As the partner team*, I point my MCP client at the agreed URLs/tokens and our two systems play a
  cross-team series whose results match field-for-field.
- *As the instructor*, I receive an email whose body is **only** valid JSON conforming to the schema.

---

## 6. Functional Requirements

IDs are referenced from `TODO.md` and the test plan. **MUST** = required for a passing submission.

### 6.1 Game engine & rules

- **FR-1 (MUST)** Maintain authoritative game state: positions of Cop, Thief, and all barriers on a
  grid of configurable size (default 5×5).
- **FR-2 (MUST)** Enforce turn order: **Thief moves first**, then Cop, alternating.
- **FR-3 (MUST)** Support 8-directional movement (including diagonals), one cell per move.
- **FR-4 (MUST)** Allow the Cop, on its turn, to **place a barrier** on its current cell instead of
  moving; max **5 barriers per sub-game**; the Thief can never place barriers.
- **FR-5 (MUST)** Treat a barrier cell as impassable for both players; **stepping into a barrier is
  illegal and loses the sub-game** for the player who did it.
- **FR-6 (MUST)** Declare **Cop win** when the Cop lands on the Thief's cell (capture = same-cell
  occupancy checked after a move). **Thief win** when the Thief survives all 25 moves.
- **FR-7 (MUST)** Cap each sub-game at **25 moves** (= 25 Thief moves; the Cop's reply to the 25th
  Thief move is the last capture chance — shared rules §2.8).
- **FR-8 (MUST)** Run a series of **6 sub-games** and aggregate results.
- **FR-9 (MUST)** Reject illegal actions (off-board, into a barrier, a 6th barrier, no action) per the
  configured policy; in the internal game an illegal action is a programming bug to fix.

### 6.2 Scoring

- **FR-10 (MUST)** Score each sub-game: Cop win → Cop 20 / Thief 5; Thief win → Cop 5 / Thief 10
  (assignment §4.4).
- **FR-11 (MUST)** Aggregate totals; document that a full series ranges **30–90** points per group.

### 6.3 Partial observability & messaging

- **FR-12 (MUST)** Each agent always knows its own cell; it sees the opponent and barriers **only**
  within `vision_radius` (default 2, king-move/Chebyshev distance). See
  [`PRD_partial_observability.md`](PRD_partial_observability.md).
- **FR-13 (MUST)** Place start positions so Cop and Thief begin **outside** each other's vision
  radius (shared rules §2.9).
- **FR-14 (MUST)** Each turn carries a free natural-language `message` (may bluff) plus a structured
  `action`; the **action is authoritative** and validated by the referee (shared rules §2.2).
- **FR-15 (SHOULD)** Agents may use received messages + memory to reason about the opponent when it
  is outside the vision radius.

### 6.4 MCP & orchestration

- **FR-16 (MUST)** Run **two independent MCP servers**, one for the Cop and one for the Thief,
  preferably with FastMCP. See [`PRD_mcp_servers.md`](PRD_mcp_servers.md).
- **FR-17 (MUST)** MCP servers expose tools/resources/prompts but **do not host the LLM**.
- **FR-18 (MUST)** The orchestrator (MCP client) manages game flow, calls the LLM API, handles tool
  calls, and calls the MCP servers.
- **FR-19 (MUST)** Each MCP server exposes at least: `get_observation`, `submit_turn`,
  `receive_message`, `validate_action`, `get_match_status`, `health_check`.

### 6.5 Reporting

- **FR-20 (MUST)** At the end of 6 clean sub-games, automatically send one email to
  `rmisegal+uoh26b@gmail.com` whose **body is only the JSON report** (no extra text), via the Gmail
  API. See [`PRD_gmail_reporting.md`](PRD_gmail_reporting.md).
- **FR-21 (MUST)** Produce the internal-game JSON (§13.1) and, for the bonus, the inter-group JSON
  (§13.2).

### 6.6 Reliability & automation

- **FR-22 (MUST)** Treat any technical failure (server crash, network glitch, LLM error mid-sub-game)
  as a **Technical Loss**: void the sub-game and rerun until there are **6 clean sub-games**
  (assignment §9; shared rules §4).
- **FR-23 (MUST)** Route every external API call (LLM, Gmail, peer MCP) through an **API Gatekeeper**
  handling rate limits, queueing, retries, logging, monitoring (guidelines §5).
- **FR-24 (SHOULD)** Stay around **30 requests/min per direction** and retry transient errors
  (shared rules §3).

### 6.7 Configuration & security

- **FR-25 (MUST)** Read all tunable parameters from config (`config.yaml`/`config.json`), never from
  hard-coded literals (§12).
- **FR-26 (MUST)** Use HTTPS-only for public MCP URLs and token authentication (with revoke) for the
  bonus match (assignment §6).
- **FR-27 (MUST)** Never commit secrets; provide `.env-example` with dummy values; `.gitignore` must
  list `.env`, `credentials.json`, `token.json`, `*.pem`, `*.key`.

### 6.8 GUI & logging

- **FR-28 (SHOULD)** Provide a GUI visualizing the board, agents, barriers, current turn, each
  agent's observation, exchanged messages, running scores, and logs (assignment §12).
- **FR-29 (MUST)** Keep full timestamped logs of every message and action and support replay
  (assignment §11; shared rules §3). See [`PRD_gui_and_logs.md`](PRD_gui_and_logs.md).

---

## 7. Non-Functional Requirements

Mapped to **ISO/IEC 25010** product-quality characteristics (guidelines §13).

| ISO/IEC 25010 attribute | Requirement |
|---|---|
| **Functional suitability** | All MUST functional requirements implemented and verified by tests |
| **Performance efficiency** | A full local series completes within a reasonable wall-clock budget; per-turn LLM latency budget configurable (default 30 s/turn — shared rules §2.5); stay ~30 req/min/direction |
| **Compatibility** | Two independently built engines interoperate via the shared JSON contract; cross-platform (Linux/macOS/Windows) |
| **Usability** | One-command run; clear README user manual; GUI follows Nielsen heuristics; clear error messages |
| **Reliability** | Technical-Loss handling + retries → 6 clean sub-games; graceful degradation; ≥85% test coverage |
| **Security** | HTTPS-only public URLs; token auth + revoke; least-privilege Gmail scope; no secrets in code |
| **Maintainability** | SDK boundary; modular files ≤150 code lines; OOP/no-duplication; ADRs; Ruff-clean |
| **Portability** | `uv`-managed environment; config-driven; containerizable/cloud-deployable |

Additional NFRs from the guidelines:

- **NFR-Cost (MUST)** Maintain an LLM/API **token cost analysis** (input/output tokens, cost per
  model, per-series estimate) — guidelines §11.
- **NFR-Research (MUST)** Maintain a **research/analysis plan**: experiments, parameter-sensitivity,
  charts, logs, screenshots — guidelines §9.
- **NFR-Version (MUST)** Track version starting at **1.00** in `src/<package>/shared/version.py`,
  the main config `version`, and `rate_limits.version` — guidelines §8.1.
- **NFR-Prompts (MUST)** Maintain a **prompt log / prompt book** documenting significant prompts —
  guidelines §8.3.

---

## 8. Game Rules (authoritative summary)

> Source: assignment §4 + `SHARED_MATCH_RULES.md`. These are FIXED unless noted as config-tunable.

- **Board:** grid, default **5×5**, size read from config (not hard-coded). Coordinates are
  `[row, col]`, origin `[0,0]` top-left, rows increase downward, columns increase rightward
  (shared rules §2.3).
- **Sub-game:** max **25 moves**. Turn-based; **Thief moves first**, then Cop, repeat. "25 moves" =
  25 Thief moves; Thief wins if it finishes the 25th move uncaught, with the Cop's reply as the last
  capture chance.
- **Each turn:** a player **must** either move exactly one cell (8-directional, diagonals allowed) or
  (Cop only) place a barrier on its current cell.
- **Barriers:** Cop only; max **5 per sub-game**; impassable to both; the Cop stands on the cell the
  turn it places it, is blocked from the next turn on, and moves off it on its following turn; a Cop
  may not place a barrier on the Thief's cell or on an existing barrier (shared rules §2.7).
- **Stepping into a barrier** = that player loses the sub-game.
- **Capture:** Cop and Thief on the **same cell**, checked after each move. Swapping cells in one
  turn (passing through each other) is **not** a capture (shared rules §2.10).
- **Win conditions:** Cop wins by capture; Thief wins by surviving all 25 moves.
- **Series:** **6 sub-games**.
  - *Internal (required) game:* both Cop and Thief agents belong to the **same group**.
  - *Bonus inter-group game:* sub-games **1–3** = Team A Cop vs Team B Thief; sub-games **4–6** =
    Team B Cop vs Team A Thief.
- **Scoring per sub-game:** Cop win → Cop 20 / Thief 5; Thief win → Cop 5 / Thief 10. Max group
  series score **90**, min **30**.
- **Start positions:** random per sub-game from a shared seed (or fixed), Cop and Thief never on the
  same cell, always outside each other's vision radius.

Full rule details and edge cases live in [`PRD_game_engine.md`](PRD_game_engine.md).

---

## 9. MCP / Orchestration Requirements

- Two **independent** MCP servers (Cop, Thief), preferably **FastMCP**. Each exposes tools,
  resources, and prompts but **does not host the LLM**.
- The **orchestrator / MCP client** owns the game loop: it calls the LLM API for the active agent,
  receives the LLM's intended tool call / action, calls the MCP server to validate/commit, and
  advances the referee.
- Development proceeds in stages (assignment §6, §13):
  1. **Localhost** — two MCP servers on separate ports.
  2. **Full local pipeline** — both agents + engine play a complete clean series locally.
  3. **Cloud / public deployment** — e.g., Prefect Cloud or equivalent.
  4. **Secure URLs + token authentication** (HTTPS-only, revwhen done).
  5. **Inter-group match support**.
- **LLM options:** recommended cloud LLM API (OpenAI / Anthropic / Gemini); optional local Ollama
  **only** if kept loopback-local or securely tunneled (ngrok Traffic Policy / Nginx reverse proxy
  with auth + HTTPS); hybrid (local orchestrator + LLM client, cloud MCP servers) is acceptable.
  **Never** expose Ollama directly without HTTPS + auth.

Detailed tool contracts, server design, and the orchestrator loop are in
[`PRD_mcp_servers.md`](PRD_mcp_servers.md) and [`PLAN.md`](PLAN.md).

---

## 10. Agent Behavior & Natural-Language Communication

- Each agent reasons over its **legal partial observation** only (its own cell + opponent/barriers
  within `vision_radius`).
- Each turn produces a **`message`** (free natural language, may bluff/deceive) and a structured
  **`action`** (`move` or `barrier` with a target cell). The referee decides on the `action`, never
  on the text.
- Outside the vision radius an agent has **no ground truth** about the opponent — only prior messages
  and its own memory. Bluffing is an intended, in-game feature; messages must nonetheless be
  **well-formed** so neither server trips over a bad payload (shared rules note §3).
- **Baseline strategy** is heuristic (distance/Manhattan/Chebyshev + barrier placement). **Optional**
  tabular Q-Learning (assignment §8) may improve adaptive play. Strategy details and the bluff
  policy are in [`PRD_agent_strategy.md`](PRD_agent_strategy.md).

---

## 11. Partial Observability / Dec-POMDP Formulation

The game is modeled as a **Decentralized Partially Observable Markov Decision Process (Dec-POMDP)**,
the tuple (assignment §11):

```
⟨ n, S, {Aᵢ}, P, R, {Ωᵢ}, O, γ ⟩
```

- **n** — number of agents (2).
- **S** — state space: positions of Cop, Thief, and the set of barriers on the grid.
- **{Aᵢ}** — per-agent actions: the 8 moves and (Cop only) barrier placement.
- **P** — transition function (deterministic given legal actions).
- **R** — reward / scoring function (the scoring table).
- **{Ωᵢ}** — per-agent partial-observation spaces (own cell + within-radius view).
- **O** — observation function (the referee tool returns each agent's legal view).
- **γ** — discount factor (used by optional Q-Learning).

The full formal model, the observation function, and the README-level Dec-POMDP write-up are in
[`PRD_partial_observability.md`](PRD_partial_observability.md).

---

## 12. Configuration Requirements

All game and system parameters MUST come from config files (`config.yaml`/`config.json`) — never
hard-coded (assignment §10; guidelines §7.2). Minimum documented keys:

| Key | Description | Default |
|---|---|---|
| `grid_size` | Grid dimensions `[rows, cols]` | `[5, 5]` |
| `max_moves` | Max moves (Thief moves) per sub-game | `25` |
| `num_games` | Sub-games per series | `6` |
| `max_barriers` | Max barriers the Cop may place per sub-game | `5` |
| `vision_radius` | King-move (Chebyshev) vision radius | `2` |
| `movement_mode` | Movement model | `eight_directional` |
| `scoring.cop_win` | Cop points on capture | `20` |
| `scoring.thief_win` | Thief points on escape | `10` |
| `scoring.cop_loss` | Cop points when Thief escapes | `5` |
| `scoring.thief_loss` | Thief points when captured | `5` |
| `rate_limits.version` | Rate-limit config version | `"1.00"` |
| `rate_limits.services.default.requests_per_minute` | Default per-service rate cap | `30` |
| `auth.*` | Token auth settings (token source, header name, revoke) | `TODO` |
| `mcp.cop_url` / `mcp.thief_url` | MCP server URLs | `TODO` |
| `llm.provider` / `llm.model` | LLM provider and model | `TODO` |
| `report.recipient` | Gmail recipient | `rmisegal+uoh26b@gmail.com` |
| `logging.*` | Logging paths/levels | `TODO` |
| `seed` / `start_mode` | Random seed / fixed-start mode | `TODO` |

Secrets (API keys, tokens) come from **environment variables / `.env`**, never config or code.
Config schema validation runs at startup, including a version-compatibility check.

---

## 13. Reporting / Email Requirements

At the end of 6 clean sub-games, the reporting component sends **one** email to
`rmisegal+uoh26b@gmail.com` via the **Gmail API**; the **email body contains only the JSON report**
(no surrounding text), so automated graders can parse it. Setup uses OAuth Client ID (Desktop app),
External audience + the Gmail account as a Test user, producing `credentials.json` + `token.json`
(never committed). Least-privilege Gmail scope is documented in
[`PRD_gmail_reporting.md`](PRD_gmail_reporting.md).

### 13.1 Internal game JSON (assignment §9.1)

```json
{
  "group_name": "Team-Name",
  "students": [],
  "github_repo": "https://github.com/...",
  "cop_mcp_url": "https://...",
  "thief_mcp_url": "https://...",
  "timezone": "Asia/Jerusalem",
  "sub_games": [],
  "totals": {
    "cop": 0,
    "thief": 0
  }
}
```

### 13.2 Bonus inter-group JSON (assignment §9.2)

```json
{
  "report_type": "bonus_game",
  "groups": {
    "group_1": "Team-A",
    "group_2": "Team-B"
  },
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
  "totals_by_group": {
    "Team-A": 0,
    "Team-B": 0
  },
  "bonus_claim": {
    "Team-A": 0,
    "Team-B": 0
  },
  "mutual_agreement": true
}
```

The exact per-sub-game record shape inside `sub_games` is specified in
[`PRD_gmail_reporting.md`](PRD_gmail_reporting.md) and validated by a JSON-schema test.

---

## 14. Bonus Match Requirements

The optional inter-group bonus (up to **10 points** toward the final project, within one week of
publication) is a friendly cross-team cloud match. Fixed rules: 6 sub-games with the role split in
§8; higher series total → 10, other → 7, exact tie → 5 each; final bonus = **average over all valid
series**; playing multiple teams is allowed and encouraged. **Both teams must email identical JSON
(`mutual_agreement: true`); any mismatch voids the bonus (0/0).** Full operational protocol,
referee-authority choice, and handshake are in [`PRD_bonus_match.md`](PRD_bonus_match.md) and
`SHARED_MATCH_RULES.md`.

---

## 15. Security / Secrets Requirements

- **HTTPS-only** for all public MCP URLs; **token authentication** in an `Authorization` header for
  the bonus match; revoke tokens after the match (assignment §6; shared rules §3).
- **No secrets in code or config.** API keys and tokens come from environment variables / `.env`.
- **`.env-example`** with dummy values is committed; real `.env` is git-ignored.
- **`.gitignore`** must include `.env`, `credentials.json`, `token.json`, `*.pem`, `*.key`
  (already present in the repo root `.gitignore`).
- **Least privilege:** use the **minimum Gmail scope** needed for sending the report; document the
  reasoning (the Google guide enables `gmail.modify` + `calendar`, but Calendar is **optional** for
  this project and the report only needs to send mail).
- Never expose Ollama (or any LLM) publicly without HTTPS + auth.

---

## 16. Logging / Auditability Requirements

- Keep a **full timestamped log of every message and action** for both agents, per sub-game and per
  series (shared rules §3; assignment §11).
- Logs must support **replay** of any sub-game for debugging and for the GUI.
- All external API calls (LLM, Gmail, peer MCP) are logged through the API Gatekeeper.
- Logs are structured (one record per turn: sub-game, move number, role, observation, message,
  action, validation result, timestamp) and are swappable with the partner team after the bonus
  match. Details in [`PRD_gui_and_logs.md`](PRD_gui_and_logs.md).

---

## 17. GUI / Visualization Requirements

- A GUI (or rich CLI fallback) MUST be able to display: the board grid; Cop, Thief, and barrier
  positions; whose turn it is; each agent's current observation (fog-of-war view); the exchanged
  natural-language messages; running scores; and a live/scrollable log.
- The GUI calls the **SDK**, not internal business logic (guidelines §4.1).
- The GUI follows Nielsen's usability heuristics and includes screenshots in docs (guidelines §10).
- Visualization for the research report (learning curves, heatmaps, parameter-sensitivity charts) is
  covered by the research plan (guidelines §9). Details in
  [`PRD_gui_and_logs.md`](PRD_gui_and_logs.md).

---

## 18. Testing / Quality Requirements

From the submission guidelines:

- **TDD** (red-green-refactor); tests written before or with implementation.
- **≥85%** test coverage (`fail_under = 85`); every public function/method has at least one test
  covering happy path **and** errors.
- **Ruff** with **zero** violations (`ruff check`).
- **Mock all external APIs** (LLM, Gmail, peer MCP); **no test depends on a real external service**.
- Test files mirror `src/` structure and also obey the ≤150-line rule.
- Contract tests for MCP payloads; JSON-schema tests for both report shapes; simulation tests for
  full sub-games; Gmail API mocked tests.
- Files ≤150 non-comment, non-empty code lines; docstrings on modules/classes/public functions;
  comments explain *why*.
- `uv`-only (`uv sync`, `uv add`, `uv run pytest`, `uv lock`); no `pip`, `requirements.txt`,
  `python -m`, `venv`/`virtualenv`.

Full test strategy is in [`PLAN.md` §19](PLAN.md#19-testing-plan).

---

## 19. Acceptance Criteria

The project is **accepted** when all of the following hold:

1. **Autonomy:** one command plays a full series and emails the report with no manual steps (G1).
2. **Rules:** a referee/engine test suite proves all rules in §8 (turn order, 8-dir movement,
   barriers, capture, 25-move cap, scoring, win conditions).
3. **Partial observability:** observation tests prove agents only see within `vision_radius` and
   start outside each other's radius.
4. **MCP:** two independent servers run on separate ports/URLs; all six tools (§6.4) respond;
   contract tests pass; servers do not host the LLM.
5. **Reliability:** an injected technical failure mid-sub-game voids and reruns it; the series ends
   with exactly 6 clean sub-games.
6. **Reporting:** the email body is **valid JSON only**, matching the §13 schema (schema test green);
   sent via Gmail API with `credentials.json`/`token.json` not committed.
7. **Config-first:** changing `grid_size`/`vision_radius`/`llm.model` in config alters behavior with
   no code change; a grep test finds no hard-coded game parameters.
8. **Quality gates:** Ruff zero violations; coverage ≥85%; all files ≤150 code lines; `uv.lock` and
   `pyproject.toml` present; `.env-example` present; `.gitignore` lists all secret patterns.
9. **Docs:** `README.md` user manual + `docs/` (this PRD, PLAN, TODO, and all per-mechanism PRDs);
   Dec-POMDP formalization present; prompt book and cost analysis present.
10. **Bonus-ready (if attempted):** cloud HTTPS + token auth works; two teams produce identical JSON
    with `mutual_agreement: true`.

---

## 20. Risks and Mitigations

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| R1 | LLM latency/timeouts stall the turn loop | Stalled series | Per-turn timeout (default 30 s) + one re-prompt then concede (shared rules §2.5); gatekeeper retries |
| R2 | Rate-limit / quota errors from LLM or Gmail | Failed series | API Gatekeeper: ~30 req/min/direction, FIFO queue, backoff retries |
| R3 | Two engines disagree on coordinates/rules | Bonus void | Single referee authority + shared spec; mirror-and-flag mismatch (shared rules §2.1) |
| R4 | Malformed turn payload crashes a server | Technical Loss | Strict schema validation on `message`+`action`; reject-not-crash; contract tests |
| R5 | Secrets leaked to git | Security incident | `.gitignore` + `.env-example` + pre-commit scan; secrets only via env |
| R6 | Ollama exposed publicly | Security incident | Loopback-only or tunneled with auth+HTTPS; ADR forbids direct exposure |
| R7 | Non-deterministic bugs hard to reproduce | Debug cost | Fixed seed / fixed-start mode; full timestamped logs + replay |
| R8 | Report JSON drifts from schema | Bonus void / grade loss | JSON-schema tests; both teams compare before sending |
| R9 | Files balloon past 150 lines / duplication creeps in | Quality-gate failure | SDK + modular design; extract shared modules; Ruff + line-count check in CI |
| R10 | Token cost runs high | Budget overrun | Cost analysis + budget alerts; short prompts; cheap models for warm-up |

---

## 21. Open Placeholders (fill before submission)

> Mark each as resolved in `TODO.md` Phase 0/17.

- `TODO: group_name` (our team name)
- `TODO: students` (names + IDs for `students` / `students_group_*`)
- `TODO: github_repo` URL (memory notes `github.com/yosefshanaa/HW6` — confirm before submission)
- `TODO: cop_mcp_url`, `TODO: thief_mcp_url` (cloud HTTPS URLs)
- `TODO: partner team name + their repo + their MCP URLs` (bonus)
- `TODO: seed` and `start_mode` (shared seed for start positions, or fixed cop/thief cells)
- `TODO: cloud provider` (e.g., Prefect Cloud) and tunnel choice
- `TODO: LLM provider + model` (and cost figures for the cost analysis)
- `TODO: per-turn timeout + forfeit policy` (default 30 s; one re-prompt then concede)
- `TODO: referee-authority choice` for the bonus (default: Cop-side engine is referee)

---

## 22. Supporting PRDs

Per guidelines §2.3 (a dedicated PRD for each major algorithm/mechanism):

| Document | Mechanism |
|---|---|
| [`PRD_game_engine.md`](PRD_game_engine.md) | Game engine, rules, referee/state authority |
| [`PRD_mcp_servers.md`](PRD_mcp_servers.md) | Cop & Thief MCP servers, tools, orchestrator loop |
| [`PRD_agent_strategy.md`](PRD_agent_strategy.md) | Baseline heuristic, optional Q-Learning, bluff handling |
| [`PRD_partial_observability.md`](PRD_partial_observability.md) | Dec-POMDP formulation & observation function |
| [`PRD_gmail_reporting.md`](PRD_gmail_reporting.md) | Gmail OAuth, JSON report, least-privilege scope |
| [`PRD_bonus_match.md`](PRD_bonus_match.md) | Inter-group match protocol & matching report |
| [`PRD_gui_and_logs.md`](PRD_gui_and_logs.md) | GUI/visualization, logging, replay |
