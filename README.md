# HW6 — Cop & Thief: Dual AI Agents via MCP

[![CI](https://github.com/yosefshanaa/HW6/actions/workflows/ci.yml/badge.svg)](https://github.com/yosefshanaa/HW6/actions/workflows/ci.yml)

Two autonomous AI agents — a **Cop** and a **Thief** — play a turn-based pursuit game on a
configurable grid under **partial observability** (a Dec-POMDP). Each agent is fronted by its **own
MCP server**, and they talk in free natural language where **bluffing is allowed** — but every move
is a structured, referee-validated action. An orchestrator drives the whole match autonomously: it
runs the series, enforces the rules through a single referee, logs every turn, and produces a
**JSON-only** report.

The graded core is the **orchestration, systems engineering, MCP integration, reliable automation,
logging and reporting** — *not* who wins the game.

> Assignment: Dr. Yoram Segal, *"Dual AI Agent race via MCP"* (v**1.00**).
> Full requirements & design live in [`docs/`](docs/):
> [PRD](docs/PRD.md) · [PLAN/architecture](docs/PLAN.md) · [TODO](docs/TODO.md) ·
> [one-page submission overview](docs/SUBMISSION_REPORT.md).

---

## Quick start

```bash
git clone https://github.com/yosefshanaa/HW6.git && cd HW6
uv sync                  # creates .venv from the lockfile (no pip/venv needed)

uv run cop-thief         # play a full 6-sub-game series → JSON report on stdout
uv run cop-thief-web-gui # …or watch the same series in your browser
```

That's the whole local demo — no LLM key, no cloud, no credentials required. Everything runs offline
on the baseline heuristic agents.

## Features

- **Config-driven game engine** — grid size, vision, barriers, scoring, move cap; nothing
  hard-coded ([`config/config.yaml`](config/config.yaml)).
- **Two independent MCP servers** (FastMCP) exposing six tools; the servers wrap the referee view +
  validation and **do not host the LLM**.
- **Autonomous orchestrator** — 6 sub-games, thief-first turns, **Technical-Loss void-and-rerun**,
  and a safe-move fallback so a turn never stalls.
- **Partial observability** — each agent sees only within its Chebyshev vision radius; outside it,
  it relies on the (possibly false) messages.
- **Natural-language channel with deception** — a free `message` (may bluff) plus an authoritative
  structured `action`; the referee decides on the **action**, never the text.
- **Three ways to watch** — headless JSON, terminal text boards, and a self-contained **browser GUI**
  with truth board, per-agent fog view, messages, scores, and replay.
- **Structured logging & replay** — every turn is a timestamped JSONL record; any series replays
  deterministically.
- **Reporting** — §9.1 internal + §9.2 bonus JSON report builders; a **mockable** Gmail sender with a
  JSON-only body.
- **Inter-group bonus dry-run** — a faithful two-team match on the loopback transport, with no
  external endpoints.
- **Engineering gates** — SDK facade, API Gatekeeper for every external call, **118 tests / 97.6%
  coverage**, Ruff clean, CI, files ≤ 150 lines.

## Install

[`uv`](https://docs.astral.sh/uv/) is the only package manager used here.

```bash
uv sync                 # core + dev dependencies
uv sync --extra mcp     # + FastMCP — only to run the networked MCP servers
uv sync --extra gmail   # + Google client libs — only for real email sending
```

## Run

| Mode | Command | What you get |
|---|---|---|
| **Headless** | `uv run cop-thief` | Autonomous series; **JSON-only** report on stdout |
| **Terminal GUI** | `uv run cop-thief-gui` | Text boards + fog-of-war in the terminal |
| **Browser GUI** | `uv run cop-thief-web-gui` | Live loopback GUI (board, fog, scores) with a **Play Again** button; `--output` for static export |
| **Replay** | `… --replay <path>` | Re-render a stored series/sub-game from its JSONL |
| **Bonus dry-run** | `uv run cop-thief-match` | Two-team bonus series on loopback; §9.2 JSON report |
| **MCP servers** | `uv run cop-thief-cop-server` · `…-thief-server` | Stand up the two FastMCP servers on localhost |

### Headless series

```bash
uv run cop-thief                              # JSON report on stdout (logs go to stderr)
uv run cop-thief --results-dir results        # also persist logs + report.json
uv run cop-thief --send                       # also email the report (needs credentials.json)
```

### Terminal GUI

```bash
uv run cop-thief-gui                                   # live series summary
uv run cop-thief-gui --replay results/<ts>/sub_game_1.jsonl
```

`C` = cop, `T` = thief, `#` = barrier, `.` = empty, `?` = unseen (beyond the vision radius).

### Browser GUI

Starts a tiny **loopback-only** GUI server (Python stdlib — no extra dependency, no network exposure)
and opens it in your browser. A **▻ Play Again** button runs a brand-new, **randomly seeded** series
live (a different game each press; the headless pipeline keeps its reproducible seed). In the UI, one
**"game"** = one full **6-sub-game series**.

```bash
uv run cop-thief-web-gui                                # live GUI at http://127.0.0.1:<port>/ (Ctrl+C to stop)
uv run cop-thief-web-gui --port 8800                    # pin the port (default: auto-select)
uv run cop-thief-web-gui --no-open                      # start the server without opening a browser
```

**Static export** (`--output`) writes a self-contained HTML file and exits — for screenshots and
replay evidence (the Play Again button is hidden, since a static file can't run Python):

```bash
uv run cop-thief-web-gui --no-open --output out.html              # static snapshot of a fresh series
uv run cop-thief-web-gui --replay results/<ts>/ --output out.html # static replay of a stored series
uv run cop-thief-web-gui --replay results/<ts>/sub_game_1.jsonl --output out.html  # one sub-game
```

It shows, side by side:

- **Truth Board · Referee View** — the real full board (for replay/debug).
- **Agent Fog View** — exactly what the acting agent could legally see (radius-limited; cells beyond
  the vision radius are `?`, distinct from `·` known-empty).
- **Comms feed** — each turn's natural-language `message` (bluffs included) next to the committed
  `action`.
- **Steps & scores** — a **STEP** is one round (*Thief action + Cop action*; **max 25** per sub-game,
  not 50), with Prev/Run/Next controls, a sub-game selector, and per-sub-game scores.

A curated sample page + screenshot notes: [`docs/examples/WEB_GUI.md`](docs/examples/WEB_GUI.md).

### MCP servers (localhost)

```bash
uv sync --extra mcp
uv run cop-thief-cop-server      # Cop FastMCP server   (default 127.0.0.1:8001)
uv run cop-thief-thief-server    # Thief FastMCP server (default 127.0.0.1:8002)
```

Each server exposes six tools — `get_observation`, `submit_turn`, `receive_message`,
`validate_action`, `get_match_status`, `health_check` — and **does not host the LLM**. The
orchestrator/MCP client drives the game.

## Expected outputs

Each headless/GUI run writes, under `results/<timestamp>/`:

| File | Contents |
|---|---|
| `sub_game_<n>.jsonl` | One timestamped record per turn: observation, message, action, validation, resulting state |
| `report.json` | The §9.1 internal-game report (group, sub-games, totals) |

Other commands:

- `cop-thief-web-gui` → `results/web_gui.html` (or your `--output` path).
- `cop-thief-match` → `results/match-<timestamp>/sub_game_<n>.jsonl` + `bonus_report.json` (§9.2,
  with `totals_by_group`, `bonus_claim`, `mutual_agreement: true`).

`results/` is git-ignored. A sample report lives at
[`docs/examples/sample_report.json`](docs/examples/sample_report.json).

## How the game works

5×5 grid (configurable), 8-directional movement, **Thief moves first**, max 25 thief-moves per
sub-game. The Cop may place **≤ 5 barriers** (impassable to both; stepping into one loses). The Cop
wins by landing on the Thief; the Thief wins by surviving 25 moves. Scoring: **Cop win → 20/5**,
**Thief win → 5/10**; a series is **6 sub-games**. Each agent sees the opponent and barriers only
within its **vision radius** (Chebyshev) — the game is a **Dec-POMDP** ⟨n, S, {Aᵢ}, P, R, {Ωᵢ}, O, γ⟩
(see [`docs/PRD_partial_observability.md`](docs/PRD_partial_observability.md)).

**Local (required) vs bonus (optional).**

| | Local / internal series | Bonus inter-group match |
|---|---|---|
| Who plays | **One group, both agents** — its Cop vs its Thief | Two groups, over HTTPS |
| Roles | **Fixed** Cop-vs-Thief for all 6 sub-games | **Swap**: 1–3 = A-Cop/B-Thief, 4–6 = B-Cop/A-Thief |
| Needs | Nothing external (fully offline) | Partner team + exchanged MCP URLs/tokens |
| Status | **Implemented & verified** | **Loopback dry-run implemented**; real match is external |

The "3 as cop / 3 as thief" role split is a **bonus-match** rule, not the local series. The local
dry-run `cop-thief-match` rehearses the bonus protocol on one machine: the **cop side owns the
authoritative referee** each sub-game while the thief side runs a **mirror engine**, and every turn
is reconciled with any divergence flagged ("mirror-and-flag"). See
[`SHARED_MATCH_RULES.md`](SHARED_MATCH_RULES.md) and [`docs/PRD_bonus_match.md`](docs/PRD_bonus_match.md).

### Strategies & balance (honest)

The baseline heuristic **Cop** pursues to capture and — only when it can see a distance-2 Thief
(radius 2) — drops a tactical barrier to herd an edge-pinned Thief; it is deterministic, always
legal, and never sacrifices a capture or self-traps. The heuristic **Thief** is **mobility-aware**:
it stays uncapturable, then keeps to open space and clearance from walls.

Balance on the fixed 5×5 is set by **vision radius + start spread** (team-chosen parameters, not the
fixed grid rule):

- **Local default — a balanced demo.** `vision_radius: 1` with fixed distance-3 starts
  (`start_distance_min: 3`, `start_distance_max: 3`) and competent, non-looping agents yields a
  **genuine contest (~54% Cop** over seeds 1000–1029, 98 Cop / 82 Thief). At radius 1 the Cop can't
  see a distance-2 Thief, so barriers stay dormant and it pursues/searches (the blind Cop patrols
  instead of oscillating — the old loop that produced repetitive draws is fixed).
- **Radius 2 (bonus-match setting) is Cop-favored.** With near-full visibility on the tiny board the
  Cop barrier-herds a competent evader to a near-certain capture; the
  [barrier ablation](docs/EXPERIMENTS.md#barrier-ablation-cop-win-rate-with-vs-without-barriers)
  shows barriers flip the game **0% → 100%** there. This is expected pursuit-evasion, and it is
  *symmetric* across the role split, so the bonus stays fair.

Full study: [`docs/EXPERIMENTS.md`](docs/EXPERIMENTS.md).

## Architecture

All consumers (CLI, GUI, reporting) go through the **SDK** facade
(`cop_thief.sdk.sdk.CopThiefSDK`); every external API call goes through the **API Gatekeeper**
(rate limits, retries, logging).

| Component | Module | Role |
|---|---|---|
| Orchestrator | `orchestrator/` | Drives the 6-sub-game series, turn loop, Technical-Loss rerun |
| MCP client / transport | `agents/agent_client.py` | Calls the servers' tools (in-process or networked) |
| Cop MCP server | `mcp/cop_server.py` | FastMCP server exposing the six tools for the Cop side |
| Thief MCP server | `mcp/thief_server.py` | FastMCP server for the Thief side |
| Referee / engine | `engine/` | Single authoritative state machine: rules, movement, capture, scoring, fog |
| Strategies | `agents/strategy/` | Heuristic Cop/Thief (+ optional tabular Q-learning core) |
| Reporting | `reporting/` | §9.1 internal + §9.2 bonus JSON; mockable Gmail sender |
| Logging / replay | `shared/replay.py` | Per-turn JSONL records; deterministic replay for GUI/audit |
| Bonus dry-run | `match/` | Two-team loopback match (authoritative + mirror referees) |

Per-turn flow: **observe → decide (strategy) → compose message → validate → commit (referee) →
deliver message → log**. The agents run on heuristics with no LLM by default; a provider-agnostic
LLM seam exists for future wiring (`config: llm.provider: none`).

## Configuration

All tunables live in [`config/`](config/) — never hard-coded:

- `config/config.yaml` — grid, moves, sub-games, barriers, vision radius, scoring, start mode/seed,
  `start_distance_max`, agents/LLM, MCP URLs, `match.vision_radius`, report recipient, logging.
- `config/rate_limits.json` — API Gatekeeper limits (version `1.00`).
- `config/logging_config.json` — logging.

Secrets come from the environment only — copy `.env-example` → `.env` and fill it in
(`.env`, `credentials.json`, `token.json`, `*.pem`, `*.key` are git-ignored). Change the board
without touching code:

```yaml
grid_size: [7, 7]
vision_radius: 3
```

## Reporting (Gmail)

After 6 clean sub-games the report is built, persisted, and printed. With `uv run cop-thief --send`
**and** a `credentials.json` present, it is also emailed to `rmisegal+uoh26b@gmail.com` with a
**JSON-only** body via the Gmail API (least-privilege `gmail.send` scope). The send path is
**mockable and fully tested without credentials**; a real live send still needs the team's Google
OAuth setup (documented in [`docs/PRD_gmail_reporting.md`](docs/PRD_gmail_reporting.md)). Without
`credentials.json`, `--send` logs a warning and writes the report without sending (stdout stays pure
JSON).

## Develop & verify

```bash
uv run pytest                 # full test suite (unit + integration)
uv run pytest --cov           # with coverage (gate: ≥ 85%)
uv run ruff check             # lint (zero violations required)
uv run python notebooks/parameter_sweep.py   # local parameter-sensitivity sweep
```

Latest local run: **118 passed**, **97.6% coverage**, **0 lint violations**.

## What is complete

Implemented and verified **locally, offline** (no LLM/cloud/credentials):

- Config-driven engine, partial observability, baseline heuristic agents (+ Q-learning core).
- Orchestrator with Technical-Loss rerun; six-tool MCP layer with schema-validated payloads and
  contract tests; SDK + API Gatekeeper.
- Natural-language `message` channel (bluffing) with authoritative validated `action`.
- §9.1 internal + §9.2 bonus report builders; **mockable** Gmail sender (JSON-only body).
- Terminal + browser GUIs with fog views and replay; structured JSONL logging.
- Inter-group **loopback dry-run** (`cop-thief-match`) with mirror-and-flag reconciliation.
- CI, 118 tests / 97.6% coverage, Ruff clean.

## External inputs still needed

These are **documented, not faked** — the code paths exist and are mock-tested; only real
accounts/credentials are missing (full list:
[`docs/TODO.md` §External Inputs Needed](docs/TODO.md#external-inputs-needed)):

| Needed | Unblocks |
|---|---|
| **Team name + student names/IDs** | `report.group_name`/`students` (currently `TODO:` placeholders in config) |
| **Google account + OAuth** (`credentials.json`/`token.json`) | A real live Gmail send |
| **Cloud provider + `MCP_AUTH_TOKEN`** | HTTPS deploy + live bearer enforcement; real `cop_mcp_url`/`thief_mcp_url` |
| **Partner team + their 4 MCP URLs/tokens** | A real bonus inter-group match |
| **LLM provider/model + API key** | LLM-driven agents + real token-cost numbers |

> Not claimed as done: **cloud HTTPS deployment** and a **live Gmail send** are not run in this repo
> (a local-testable bearer-token check exists; the cloud wiring is the external stage).

## Project layout

```
src/cop_thief/    domain · engine · orchestrator · agents · mcp · reporting · gui · match · shared · sdk
tests/            unit + integration (mirrors src/)
config/           config.yaml · rate_limits.json · logging_config.json
docs/             PRD · PLAN · TODO · per-mechanism PRDs · SUBMISSION_REPORT · EXPERIMENTS · …
prompts/          PROMPT_BOOK · turn_templates
notebooks/        parameter_sweep.py (local experiment)
results/          per-series logs + report.json (git-ignored)
```

## Documentation

| Doc | What |
|---|---|
| [`docs/SUBMISSION_REPORT.md`](docs/SUBMISSION_REPORT.md) | One-page submission overview |
| [`docs/PRD.md`](docs/PRD.md) · [`PLAN.md`](docs/PLAN.md) · [`TODO.md`](docs/TODO.md) | Requirements · architecture/ADRs · task tracking |
| `docs/PRD_*.md` | Per-mechanism PRDs (engine, MCP, strategy, partial-observability, Gmail, bonus, GUI/logs) |
| [`docs/EXPERIMENTS.md`](docs/EXPERIMENTS.md) | Local parameter-sensitivity study + balance analysis |
| [`docs/COST_ANALYSIS.md`](docs/COST_ANALYSIS.md) | LLM token cost model + optimization |
| [`docs/QUALITY_MAPPING.md`](docs/QUALITY_MAPPING.md) | ISO/IEC 25010 evidence map |
| [`prompts/PROMPT_BOOK.md`](prompts/PROMPT_BOOK.md) · [`turn_templates.md`](prompts/turn_templates.md) | Prompt log + LLM turn templates |
| [`SHARED_MATCH_RULES.md`](SHARED_MATCH_RULES.md) | Shared spec for the inter-group bonus match |

## License

MIT (see `pyproject.toml`). Third-party libraries retain their own licenses.
