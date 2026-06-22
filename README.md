# HW6 — Cop & Thief: Dual AI Agents via MCP

[![CI](https://github.com/yosefshanaa/HW6/actions/workflows/ci.yml/badge.svg)](https://github.com/yosefshanaa/HW6/actions/workflows/ci.yml)

Two autonomous AI agents — a **Cop** and a **Thief** — play a turn-based pursuit game on a
configurable grid under **partial observability**, each fronted by its own **MCP server** and
communicating in natural language (bluffing allowed). The graded core is the **orchestration,
systems engineering, MCP integration, reporting, and reliable automation** — not the game outcome.

Assignment: Dr. Yoram Segal, *"Dual AI Agent race via MCP"*. Version **1.00**.

> Full requirements, architecture, and task tracking live in [`docs/`](docs/):
> [PRD](docs/PRD.md) · [PLAN](docs/PLAN.md) · [TODO](docs/TODO.md) and the per-mechanism
> `PRD_*.md` files.

---

## Requirements

- [`uv`](https://docs.astral.sh/uv/) (the only package manager used here — no `pip`/`venv`).
- Python ≥ 3.10 (uv provisions an interpreter automatically).

## Install

```bash
git clone https://github.com/yosefshanaa/HW6.git && cd HW6
uv sync                 # core + dev dependencies; creates .venv and uv.lock
uv sync --extra mcp     # add FastMCP (only needed to run the network MCP servers)
uv sync --extra gmail   # add Google client libs (only needed for real email sending)
```

## Run the autonomous pipeline (local MVP)

Plays a full clean series of 6 sub-games with the baseline heuristic agents and prints the
**JSON-only** report to stdout (the same body the Gmail reporter would email):

```bash
uv run cop-thief
uv run cop-thief --results-dir results        # also writes logs + report.json there
uv run cop-thief --send                       # also email the report (needs credentials.json)
```

`--send` emails the JSON-only report to `report.recipient` via the Gmail API when
`credentials.json` is present; without it, the run logs a warning and writes the report without
sending (stdout stays pure JSON). See [Reporting](#reporting-gmail).

Each run writes, under `results/<timestamp>/`:
- `sub_game_<n>.jsonl` — a timestamped record of every turn (observation, message, action,
  validation, resulting state) for replay/audit.
- `report.json` — the §9.1 internal-game report.

### Three ways to watch a match

| Mode | Command | What you get |
|---|---|---|
| **Headless** | `uv run cop-thief` | Autonomous run; JSON-only report on stdout |
| **Terminal GUI** | `uv run cop-thief-gui` | Text boards + fog-of-war in the terminal |
| **Browser GUI** | `uv run cop-thief-web-gui` | A local, self-contained HTML page (board, fog, slider, log, scores) |
| **Match dry-run** | `uv run cop-thief-match` | Two-team bonus series on loopback; §9.2 JSON report (see [below](#inter-group-match-dry-run-phase-12-de-risking)) |

#### Terminal GUI (text)

```bash
uv run cop-thief-gui                                   # live series summary
uv run cop-thief-gui --replay results/<ts>/sub_game_1.jsonl
```

(`C` = cop, `T` = thief, `#` = barrier, `.` = empty; `?` = unseen in the fog view.)

#### Browser GUI

Renders a **self-contained local HTML page** (no network/CDN) and opens it in your default browser.
It clearly separates the two views and counts in **steps**, not raw turns:

- **Truth Board · Referee View** — the actual full board (replay/debug).
- **Agent Fog View · <agent>'s observation** — what the acting agent could legally see (radius-limited;
  unknown cells beyond the vision radius are marked `?`, distinct from `·` known-empty).
- **STEP** = one round = *Thief action + Cop action* (**max 25** per sub-game, not 50). Each step has
  two turns; the **Thief / Cop PHASE** buttons inspect each agent's view within the step.
- Sub-game selector, **⏮ Prev / ▶ Run / Next ⏭** + speed, a legend (`C`/`T`/`▦`/`·`/`?`), the comms
  feed, and scores.

```bash
uv run cop-thief-web-gui                               # play a fresh series, then open it
uv run cop-thief-web-gui --replay results/<ts>/        # replay a whole series directory
uv run cop-thief-web-gui --replay results/<ts>/sub_game_1.jsonl   # replay one sub-game
uv run cop-thief-web-gui --no-open --output out.html   # just write the HTML (e.g. headless)
```

A curated sample page + screenshot notes are in
[`docs/examples/WEB_GUI.md`](docs/examples/WEB_GUI.md).

### MCP servers (localhost)

```bash
uv sync --extra mcp
uv run cop-thief-cop-server      # Cop FastMCP server   (default 127.0.0.1:8001)
uv run cop-thief-thief-server    # Thief FastMCP server (default 127.0.0.1:8002)
```

Each server exposes the six tools (`get_observation`, `submit_turn`, `receive_message`,
`validate_action`, `get_match_status`, `health_check`) and **does not host the LLM**. The
orchestrator/MCP client drives the game and (in cloud mode) calls the LLM provider.

### Inter-group match dry-run (Phase 12 de-risking)

```bash
uv run cop-thief-match                          # local two-team series; §9.2 JSON on stdout
uv run cop-thief-match --results-dir results    # also writes logs + bonus_report.json there
```

Models **two independent team systems on one machine** playing the fixed 6-sub-game bonus series
over the loopback MCP transport — a faithful rehearsal of the real cross-team match with **zero
external endpoints**. Per the [shared spec](SHARED_MATCH_RULES.md), the **cop side owns the
authoritative referee** each sub-game while the thief side runs a **mirror engine**; every committed
turn is reconciled and any divergence is **flagged** (the "mirror-and-flag" rule). Roles **swap at
sub-game 4**, and the run emits the §9.2 report with `totals_by_group`, `bonus_claim`, and
`mutual_agreement: true`. With two identical heuristic peers the series is a symmetric 75–75 tie and
the engines reconcile cleanly. To play a **real** partner, the same orchestration points at their
four MCP URLs + tokens (exchanged out of band) instead of the loopback transport.

## Configuration

All tunables live in [`config/`](config/) — never hard-coded:

- `config/config.yaml` — grid size, max moves, sub-games, barriers, vision radius, scoring,
  start mode/seed, agents/LLM, MCP URLs, report recipient, logging.
- `config/rate_limits.json` — API Gatekeeper limits (version `1.00`).
- `config/logging_config.json` — logging.

Secrets come from the environment only. Copy `.env-example` → `.env` and fill it in
(`.env`, `credentials.json`, `token.json`, `*.pem`, `*.key` are git-ignored).

Example (change grid + radius without touching code):

```yaml
grid_size: [7, 7]
vision_radius: 3
```

## Game rules (summary)

5×5 grid (configurable), 8-directional movement, **Thief moves first**, max 25 moves/sub-game.
The Cop may place ≤5 barriers (impassable to both); stepping into a barrier loses. Cop wins by
landing on the Thief; the Thief wins by surviving 25 moves. Scoring: Cop win → 20/5, Thief win →
5/10. A series is 6 sub-games. Each agent sees the opponent/barriers only within its vision radius
(Chebyshev) — the game is a **Dec-POMDP** ⟨n, S, {Aᵢ}, P, R, {Ωᵢ}, O, γ⟩
(see [`docs/PRD_partial_observability.md`](docs/PRD_partial_observability.md)).

The baseline heuristic **Cop** pursues to capture and — when it can see a distance-2 Thief (radius 2) —
**drops a tactical barrier** to herd a near, edge-pinned Thief, deterministic, always legal, and never
sacrificing an available capture or self-trapping. The heuristic **Thief** is **mobility-aware**: it
stays uncapturable (≥2 cells from the Cop), then keeps to open space and clearance from walls instead
of fleeing into a corner (see [`docs/PRD_agent_strategy.md`](docs/PRD_agent_strategy.md)).

**Balance is set by the vision radius (a team-chosen parameter, not the fixed 5×5 rule) plus the start
spread.** The **local series defaults to radius 1 with a start-distance cap (`start_distance_max: 3`)**,
which removes pathological far-corner starts and gives a **roughly even contest (~49% Cop over seeds
1000–1029)**. At radius 1 the Cop can't see a distance-2 Thief, so it plays pure pursuit and barriers
stay dormant. Raise vision to **radius 2** — the value the **bonus inter-group match** uses
(`match.vision_radius`) — and the 5×5 board is near-fully observed: the Cop barrier-herds a competent
evader to a near-certain capture, and the [barrier ablation](docs/EXPERIMENTS.md#barrier-ablation-cop-win-rate-with-vs-without-barriers)
shows barriers flip the game **0%→100%** there (they are decisive at r2, inoperative at r1). That Cop
dominance is expected pursuit-evasion on a tiny, fully-seen board — and *symmetric* across the role
split, so the bonus stays fair; see [`docs/EXPERIMENTS.md`](docs/EXPERIMENTS.md).

## Reporting (Gmail)

At the end of 6 clean sub-games the report is built and printed; with `uv run cop-thief --send`
(and a `credentials.json` present) it is also emailed to `rmisegal+uoh26b@gmail.com` with a
**JSON-only** body via the Gmail API (least-privilege `gmail.send` scope). The send path is
mockable and fully tested without credentials; the real OAuth setup (Desktop app, External
audience + Test user, `credentials.json`/`token.json`) is documented in
[`docs/PRD_gmail_reporting.md`](docs/PRD_gmail_reporting.md).

## Develop & verify

```bash
uv run pytest                 # run the test suite
uv run pytest --cov           # with coverage (target ≥ 85%)
uv run ruff check             # lint (zero violations required)
uv add <pkg>                  # add a dependency
uv lock                       # refresh the lockfile
```

## Project layout

```
src/cop_thief/    domain · engine · orchestrator · agents · mcp · reporting · gui · shared · sdk
tests/            unit + integration (mirrors src/)
config/           config.yaml · rate_limits.json · logging_config.json
docs/             PRD · PLAN · TODO · per-mechanism PRDs · SUBMISSION_REPORT · EXPERIMENTS · COST_ANALYSIS · QUALITY_MAPPING · examples/
prompts/          PROMPT_BOOK · turn_templates
notebooks/        parameter_sweep.py (local experiment)
results/          per-series logs + report.json (git-ignored)
```

All consumers (CLI, GUI, reporting) call the **SDK** (`cop_thief.sdk.sdk.CopThiefSDK`); every
external API call goes through the **API Gatekeeper**.

## Status & remaining inputs

The local pipeline is complete and verified (104 tests, 97% coverage, ruff clean, autonomous
JSON-only report). See [`docs/SUBMISSION_REPORT.md`](docs/SUBMISSION_REPORT.md) for a one-page
overview. Items still gated on **external** accounts/credentials (live Gmail send, cloud HTTPS
deploy, partner bonus match, team/student details, LLM key) are listed in
[`docs/TODO.md` §External Inputs Needed](docs/TODO.md#external-inputs-needed) — these are documented,
not faked.

## Documentation

| Doc | What |
|---|---|
| [`docs/SUBMISSION_REPORT.md`](docs/SUBMISSION_REPORT.md) | One-page submission overview |
| [`docs/PRD.md`](docs/PRD.md) · [`PLAN.md`](docs/PLAN.md) · [`TODO.md`](docs/TODO.md) | Requirements · architecture/ADRs · task tracking |
| `docs/PRD_*.md` | Per-mechanism PRDs (engine, MCP, strategy, partial-observability, Gmail, bonus, GUI/logs) |
| [`docs/EXPERIMENTS.md`](docs/EXPERIMENTS.md) | Real local parameter-sensitivity study |
| [`docs/COST_ANALYSIS.md`](docs/COST_ANALYSIS.md) | LLM token cost model + optimization |
| [`docs/QUALITY_MAPPING.md`](docs/QUALITY_MAPPING.md) | ISO/IEC 25010 evidence map |
| [`prompts/PROMPT_BOOK.md`](prompts/PROMPT_BOOK.md) · [`turn_templates.md`](prompts/turn_templates.md) | Prompt log + LLM turn templates |
| [`docs/examples/`](docs/examples/) | Sample report + replay excerpt |
| [`SHARED_MATCH_RULES.md`](SHARED_MATCH_RULES.md) | Shared spec for the inter-group bonus match |

## License

MIT (see `pyproject.toml`). Third-party libraries retain their own licenses.
