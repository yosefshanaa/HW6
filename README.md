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

### Text visualization / replay

```bash
uv run cop-thief-gui                                   # live series summary
uv run cop-thief-gui --replay results/<ts>/sub_game_1.jsonl
```

(`C` = cop, `T` = thief, `#` = barrier, `.` = empty.)

### MCP servers (localhost)

```bash
uv sync --extra mcp
uv run cop-thief-cop-server      # Cop FastMCP server   (default 127.0.0.1:8001)
uv run cop-thief-thief-server    # Thief FastMCP server (default 127.0.0.1:8002)
```

Each server exposes the six tools (`get_observation`, `submit_turn`, `receive_message`,
`validate_action`, `get_match_status`, `health_check`) and **does not host the LLM**. The
orchestrator/MCP client drives the game and (in cloud mode) calls the LLM provider.

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

The local pipeline is complete and verified (85 tests, 97% coverage, ruff clean, autonomous
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
