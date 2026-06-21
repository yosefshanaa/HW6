# TODO — HW6: Dual AI Agent Race via MCP Servers (Cop & Thief)

**Document:** Task tracking (`docs/TODO.md`)
**Version:** 1.00
**Companion docs:** [`PRD.md`](PRD.md), [`PLAN.md`](PLAN.md), per-mechanism `PRD_*.md`.
**Last updated:** 2026-06-22

> Status legend: `[ ]` not started · `[~]` in progress · `[x]` done.
> Priority: **P0** (must, blocks submission) · **P1** (should) · **P2** (nice-to-have).
> Owner placeholders: `@owner-TODO`. Each phase lists **dependencies** and a **Definition of Done
> (DoD)**. Phases follow the recommended development order (assignment §13) and the submission
> guidelines workflow (§2.5).

---

## Status Snapshot (2026-06-22)

**Done & verified locally** (75 tests, 97% coverage, ruff clean, pushed to `origin/main`):
- Phases 1–10, 13–14: scaffold, config/version/secrets, engine, partial observation, baseline
  agents, MCP servers/tools/client, orchestrator + Technical-Loss, logging/replay, internal+bonus
  report JSON, **mocked** Gmail reporter, SDK + CLI, GUI text renderer + replay, CI workflow,
  prompt book.
- `uv run cop-thief` plays a full clean 6-sub-game series autonomously and emits a **JSON-only**
  report to stdout (logs go to stderr).

**Blocked on external inputs (documented, not faked):**
- **Live Gmail send** — needs the team's Google account + OAuth (`credentials.json`/`token.json`);
  send path is coded + mocked-tested. See [`PRD_gmail_reporting.md`](PRD_gmail_reporting.md).
- **Cloud deployment + bearer auth over HTTPS** — needs a cloud provider + credentials (Phase 15).
  *(A local-testable bearer-token check is provided; cloud wiring is external.)*
- **Bonus inter-group match** — needs a real partner team + their MCP URLs/tokens (Phase 12).
- **Research report artifacts** — parameter study, cost analysis, ISO 25010 mapping, screenshots
  (Phase 16).

**Open placeholders (fill before submission):** team name, students, real MCP cloud URLs, cloud
provider, LLM provider/model. (`github_repo` is set to `https://github.com/yosefshanaa/HW6`.)

---

## Phase 0 — Documentation and Setup

**Deps:** none. **Owner:** `@owner-TODO`.

- [x] **P0** Read all source PDFs + `SHARED_MATCH_RULES.md`.
- [x] **P0** Write `docs/PRD.md` (21 sections) — *approve before coding*.
- [x] **P0** Write `docs/PLAN.md` (architecture, C4, domain model, ADRs).
- [x] **P0** Write `docs/TODO.md` (this file).
- [x] **P0** Write per-mechanism PRDs (engine, MCP, strategy, partial-observability, Gmail, bonus,
  GUI/logs).
- [ ] **P0** Team reviews & **approves all docs** (guidelines §2.5 step 5) before implementation.
- [~] **P1** Fill open placeholders (PRD §21): `github_repo` set ✅; **still TODO** — team name,
  students, real MCP cloud URLs, cloud provider, LLM provider/model.

**DoD:** `README.md` + `docs/` (PRD, PLAN, TODO, all `PRD_*.md`) exist and are reviewed/approved; no
code written yet.

---

## Phase 1 — Project Scaffolding

**Deps:** Phase 0 approved. **Owner:** `@owner-TODO`.

- [x] **P0** Initialize `uv` project; create `pyproject.toml` (name `cop-thief`, package
  `cop_thief`, `requires-python`).
- [x] **P0** Create the modular tree from `PLAN.md` §3 (`src/`, `tests/`, `docs/`, `config/`,
  `data/`, `results/`, `assets/`, `notebooks/`, `prompts/`).
- [x] **P0** Add `src/cop_thief/sdk/sdk.py` skeleton (SDK entry point).
- [x] **P0** Configure Ruff (`select = ["E","F","W","I","N","UP","B","C4","SIM"]`) and coverage
  (`fail_under = 85`) in `pyproject.toml`.
- [x] **P0** Confirm `.gitignore` lists `.env`, `credentials.json`, `token.json`, `*.pem`, `*.key`
  (already present) and that `uv.lock` is **not** ignored.
- [ ] **P1** Add a CI workflow: `uv sync` → `ruff check` → `uv run pytest --cov`.

**DoD:** `uv sync` succeeds; `ruff check` clean on the skeleton; empty test run green; tree matches
`PLAN.md`.

---

## Phase 2 — Config / Version / Secrets

**Deps:** Phase 1. **Owner:** `@owner-TODO`.

- [x] **P0** Author `config/config.yaml` with all keys from PRD §12 (defaults).
- [x] **P0** Author `config/rate_limits.json` (version `"1.00"`, `requests_per_minute: 30`, …).
- [x] **P0** Implement `shared/config.py` (`ConfigManager`): load + schema-validate + version check.
- [x] **P0** Implement `shared/version.py` (`__version__ = "1.00"`) and wire version into config
  checks.
- [x] **P0** Create `.env-example` with dummy `LLM_API_KEY`, token vars, Gmail placeholders.
- [x] **P0** Implement secret access via `os.environ.get(...)` only (no secrets in code/config).
- [x] **P1** Add `config/logging_config.json` + `shared/logging_setup.py`.

**DoD:** Config loads & validates; changing `grid_size` in config (no code change) is observable in a
test; version fields all read `1.00`; `.env-example` present; a grep test finds no hard-coded game
values.

---

## Phase 3 — Core Game Engine

**Deps:** Phase 2. **Owner:** `@owner-TODO`. **PRD:** [`PRD_game_engine.md`](PRD_game_engine.md).

- [x] **P0** Domain models: `Position`, `PlayerRole`, `Action`, `Barrier`, `GameState`.
- [x] **P0** `engine/movement.py` — 8-directional king-moves; apply validated move.
- [x] **P0** `engine/rules.py` — legality (bounds, single step, barrier rules, ≤5 barriers, Cop-only
  barrier, no barrier on Thief/existing barrier).
- [x] **P0** `engine/scoring.py` — scoring table (config-driven).
- [x] **P0** `engine/referee.py` — state machine: thief-first turns, capture check, 25-move cap,
  illegal-action loss, win conditions.
- [x] **P0** TDD tests first for each of the above (happy path + errors).

**DoD:** Seeded sub-game tests prove turn order, movement, barrier rules, capture, 25-move cap,
scoring, and win conditions; engine is pure (no I/O) and deterministic; coverage ≥85% for `engine/`.

---

## Phase 4 — Partial Observation / Referee

**Deps:** Phase 3. **Owner:** `@owner-TODO`. **PRD:**
[`PRD_partial_observability.md`](PRD_partial_observability.md).

- [x] **P0** `domain/observation.py` — `Observation` model.
- [x] **P0** `engine/observation_service.py` — compute legal view: own cell always; opponent +
  barriers only within `vision_radius` (Chebyshev).
- [x] **P0** Start-position generator: Cop & Thief never same cell; **outside** each other's vision
  radius; seeded / fixed-start mode.
- [x] **P0** Dec-POMDP formalization documented (tuple ⟨n,S,{Aᵢ},P,R,{Ωᵢ},O,γ⟩) — in
  PRD_partial_observability.md and now in README.
- [x] **P0** Tests: hidden opponent outside radius; visible within; start-distance invariant.

**DoD:** Observation tests prove fog-of-war and the start-distance invariant; the Dec-POMDP write-up
exists for the README.

---

## Phase 5 — Agent Strategy Baseline

**Deps:** Phase 4. **Owner:** `@owner-TODO`. **PRD:** [`PRD_agent_strategy.md`](PRD_agent_strategy.md).

- [x] **P0** `agents/strategy/base.py` — `Strategy` base class (Template Method; no duplication).
- [x] **P0** `agents/strategy/heuristic.py` — Cop pursuit; Thief evasion. *(baseline Cop uses pure
  pursuit; opportunistic barrier placement deferred — engine fully supports barriers.)*
- [x] **P1** `agents/strategy/q_table.py` — tabular Q-Learning Bellman update + greedy action.
  *(core implemented; full ε-greedy policy strategy is a future enhancement.)*
- [x] **P0** Bluff handling: heuristic never treats messages as ground truth (ignores text;
  within-radius observation overrides). Thief `compose_message` emits a decoy/bluff.
- [x] **P0** Tests: heuristic produces legal actions on partial observations; never stalls.

**DoD:** Baseline heuristic plays legal sub-games end-to-end (engine-only, no LLM) and never produces
an illegal action; optional Q-table trains on a toy run if implemented.

---

## Phase 6 — MCP Servers

**Deps:** Phase 5. **Owner:** `@owner-TODO`. **PRD:** [`PRD_mcp_servers.md`](PRD_mcp_servers.md).

- [x] **P0** `mcp/tools.py` — role-parameterized implementations of the six tools (pure, testable).
- [x] **P0** `mcp/cop_server.py`, `mcp/thief_server.py` — FastMCP apps on separate ports
  (shared `mcp/server_app.py` builder; `fastmcp` is the optional `mcp` extra).
- [x] **P0** Tools: `get_observation`, `submit_turn`, `receive_message`, `validate_action`,
  `get_match_status`, `health_check`.
- [x] **P0** Servers do **not** host the LLM; they wrap the referee view + validation only.
- [x] **P0** Schema-validate all tool payloads (reject, don't crash).
- [ ] **P1** Bearer-token auth middleware (token from env) — used in cloud stage (Phase 15).
- [x] **P0** Contract tests for each tool payload + in-process client↔server round-trip.

**DoD:** Both servers start on localhost (`:8001`/`:8002`); `health_check` returns version;
contract tests pass; a turn can be validated/committed through a server.

---

## Phase 7 — Orchestrator / Client

**Deps:** Phase 6. **Owner:** `@owner-TODO`. **PRD:** [`PRD_mcp_servers.md`](PRD_mcp_servers.md).

- [x] **P0** `agents/agent_client.py` — MCP client wrapper + in-process transport.
- [x] **P0** `agents/llm_client.py` — provider-agnostic LLM seam (via gatekeeper; responder-injected).
- [x] **P0** `orchestrator/turn_loop.py` — one turn (observe → decide → submit → deliver message →
  log).
- [x] **P0** `orchestrator/orchestrator.py` — sub-game + series loop (thief first; 6 sub-games).
- [x] **P0** `orchestrator/technical_loss.py` — void & rerun until 6 clean sub-games.
- [x] **P0** Fallback to a safe legal move when the agent returns an illegal action.
- [x] **P0** `shared/gatekeeper.py` — rate limits, queue/backpressure, retries, logging, monitoring.
- [x] **P0** Integration test: full local series completes autonomously.

**DoD:** A full 6-sub-game series runs locally end-to-end with no manual intervention; an injected
mid-sub-game failure voids and reruns that sub-game; all external calls go through the gatekeeper.

---

## Phase 8 — Natural-Language Message Handling

**Deps:** Phase 7. **Owner:** `@owner-TODO`.

- [x] **P0** Enforce the turn envelope (`sub_game`, `move_number`, `role`, `message`, `action`)
  *(formalized as the MCP `submit_turn` payload in Phase 6).*
- [x] **P0** Deliver opponent messages into peer memory (`received_messages`).
- [x] **P0** Allow bluffing in `message`; keep payloads well-formed (schema-validated).
- [ ] **P1** Prompt templates that ask the LLM for both a message and an action; log to prompt book.
- [x] **P0** Tests: a bluff message does not change adjudication (referee decides on `action`).

**DoD:** Messages flow both ways and are logged; a deceptive message never alters the referee's
outcome; prompt book records the message/action prompts.

---

## Phase 9 — Logging / Replay / Report Model

**Deps:** Phase 7. **Owner:** `@owner-TODO`. **PRD:** [`PRD_gui_and_logs.md`](PRD_gui_and_logs.md).

- [x] **P0** `domain/records.py` — `TurnRecord`, `SubGameResult` (report dict built in reporting).
- [x] **P0** `shared/replay.py` — write one `TurnRecord` per turn (JSONL in `results/`).
- [x] **P0** `reporting/report_builder.py` — assemble internal (§9.1) + bonus (§9.2) report dicts.
- [x] **P0** `reporting/schemas.py` — JSON schemas for internal + bonus reports.
- [x] **P0** Tests: replay reconstructs a sub-game; report dict validates against schema.

**DoD:** Every message+action is timestamped and logged; a sub-game replays from JSONL; the internal
report validates against schema.

---

## Phase 10 — Gmail API Reporting

**Deps:** Phase 9. **Owner:** `@owner-TODO`. **PRD:** [`PRD_gmail_reporting.md`](PRD_gmail_reporting.md).

- [ ] **P0** Complete Google OAuth setup (Gmail API enabled; Desktop app Client ID; External +
  Test user; least-privilege scope); produce `credentials.json` + `token.json` (never committed).
  *(code path ready; real OAuth needs the team's Google account — steps in PRD_gmail_reporting.md.)*
- [x] **P0** `reporting/gmail_reporter.py` — send one email; **body = JSON only**; via gatekeeper.
- [x] **P0** Wire send into the pipeline after 6 clean sub-games (`SDK.play_and_report(reporter=…)`
  → `report.recipient`). CLI default is no-send (no creds present).
- [x] **P0** Gmail-mocked tests (no real send in CI). *(one manual live smoke test still pending.)*
- [x] **P1** Document why Calendar scope is not needed (least-privilege `gmail.send`).

**DoD:** A mocked test proves a JSON-only body is sent to the recipient via the Gmail API; one live
smoke test delivers a real report; secrets are git-ignored.

---

## Phase 11 — GUI

**Deps:** Phase 9. **Owner:** `@owner-TODO`. **PRD:** [`PRD_gui_and_logs.md`](PRD_gui_and_logs.md).

- [x] **P1** `gui/app.py` — text board (C/T/#/.), agents, barriers, turn line (calls SDK).
- [ ] **P1** Per-agent observation (fog-of-war) panels. *(replay renders true resulting state;
  per-agent fogged panels not yet split out.)*
- [x] **P1** Message log + per-sub-game score lines + turn-by-turn event log (replay mode).
- [x] **P1** Replay mode (load a series JSONL via `cop-thief-gui --replay`).
- [ ] **P2** Capture screenshots into `assets/`/`results/` for the report.

**DoD:** The GUI shows board, agents, barriers, turns, observations, messages, scores, and logs for a
live or replayed series; calls only the SDK.

---

## Phase 12 — Bonus Inter-Group Interoperability

**Deps:** Phases 7, 15. **Owner:** `@owner-TODO`. **PRD:** [`PRD_bonus_match.md`](PRD_bonus_match.md).

- [ ] **P1** Agree the shared spec choices with the partner (coordinates, referee, seed, timeout) —
  `SHARED_MATCH_RULES.md`.
- [ ] **P1** Connect to partner MCP URLs with tokens; rate-limit handshake (~30 req/min/direction).
- [ ] **P1** Role split: sub-games 1–3 (A Cop vs B Thief), 4–6 (B Cop vs A Thief).
- [ ] **P1** Mirror-and-flag mismatch detection (non-referee side).
- [ ] **P1** Build the bonus report (§9.2); both teams compare and send **identical** JSON with
  `mutual_agreement: true`.
- [ ] **P1** Swap timestamped logs after the match for joint debugging.

**DoD:** A cross-team series of 6 clean sub-games runs over HTTPS+token; both teams' JSON match
field-for-field with `mutual_agreement: true`.

---

## Phase 13 — Testing and Coverage

**Deps:** Phases 3–12 (ongoing, TDD). **Owner:** `@owner-TODO`.

- [x] **P0** Unit tests mirror `src/`; public functions/methods have happy-path + error tests.
- [x] **P0** Integration tests: full sub-game, orchestrator loop, Technical-Loss rerun.
- [x] **P0** Contract tests for all MCP payloads.
- [x] **P0** Simulation tests (seeded series → expected outcomes).
- [x] **P0** Report JSON-schema tests (internal + bonus; body is JSON-only).
- [x] **P0** Gmail API mocked tests; **no test hits a real external service**.
- [x] **P0** Coverage ≥85% (`fail_under = 85`) — currently **97%**, 75 tests.

**DoD:** `uv run pytest --cov` ≥85%; all suites green; all external services mocked.

---

## Phase 14 — Lint / Format / Quality Gates

**Deps:** ongoing. **Owner:** `@owner-TODO`.

- [x] **P0** `ruff check` → **zero** violations.
- [x] **P0** All code files ≤150 non-comment, non-empty lines (largest is 127).
- [x] **P0** Docstrings on modules/classes/public functions; comments explain *why*.
- [x] **P0** No duplication (shared `mcp/tools.py` + `server_app.py`; `Strategy` base; shared helpers).
- [x] **P0** All external calls go through the gatekeeper; all logic behind the SDK.
- [x] **P0** No hard-coded configurable values (config-driven engine/scoring/radii/urls).

**DoD:** Ruff clean; line-count check passes; SDK + gatekeeper boundaries verified; no hard-coded
config values.

---

## Phase 15 — Deployment

**Deps:** Phases 6, 7. **Owner:** `@owner-TODO`.

- [ ] **P1** Local: two servers + orchestrator documented in README.
- [ ] **P1** Cloud: deploy MCP servers to a public host (e.g., Prefect Cloud).
- [ ] **P1** Public HTTPS URLs; orchestrator calls outbound.
- [ ] **P1** Token auth enabled; revoke procedure documented.
- [ ] **P2** If using Ollama: loopback-only or secure tunnel (ngrok/Nginx + auth + HTTPS); never
  exposed directly.

**DoD:** Cloud MCP servers reachable over HTTPS with token auth; a series runs against cloud URLs.

---

## Phase 16 — README / Scientific Report

**Deps:** Phases 3–13. **Owner:** `@owner-TODO`.

- [x] **P0** `README.md` as a full user manual: install, run, config guide, examples *(screenshots
  pending)*.
- [x] **P0** Dec-POMDP formalization in README (assignment §11).
- [ ] **P0** Research/analysis: parameter-sensitivity experiments, learning curves, charts, logs,
  screenshots (guidelines §9).
- [ ] **P0** LLM **cost analysis** (input/output tokens, cost per model, per-series estimate).
- [ ] **P0** **Prompt book** (`prompts/`) documenting significant prompts.
- [ ] **P1** ISO/IEC 25010 quality-attribute mapping in the report.

**DoD:** README is a complete manual; the scientific report covers Dec-POMDP, experiments, charts,
cost analysis, and prompt book.

---

## Phase 17 — Final Submission Checklist

**Deps:** all. **Owner:** `@owner-TODO`.

> Aligned to `software_submission_guidelines-V3` §17 / §20.9.

**Docs & structure**
- [ ] **P0** `README.md` (user-manual level) at repo root.
- [ ] **P0** `docs/` has PRD, PLAN, TODO + a `PRD_*.md` per major mechanism.
- [ ] **P0** Architecture documented with clear diagrams; prompt book present.

**Architecture & code**
- [ ] **P0** SDK boundary: all business logic via `sdk/sdk.py`.
- [ ] **P0** OOP, no duplication, mixins/inheritance where appropriate.
- [ ] **P0** API Gatekeeper for every external call; rate limits from config; queue management.
- [ ] **P0** Files ≤150 code lines; docstrings + *why* comments; consistent naming.

**Tests & quality**
- [ ] **P0** TDD; coverage ≥85%; Ruff zero violations; edge cases + error handling documented;
  automated test reports.

**Config & security**
- [ ] **P0** Config separate from code, versioned; `.env-example` with dummies; no API keys/secrets
  in code; `.gitignore` updated; `uv`-only; `uv.lock` + `pyproject.toml` present.

**Research & viz**
- [ ] **P0** Parameter study, analysis notebook, charts; quality graphs/screenshots; cost analysis +
  optimization notes.

**Extensibility & standards**
- [ ] **P1** Extension points; professional Python packaging; ISO/IEC 25010 compliance; tidy Git
  history, license, attribution, deployment instructions.

**Assignment-specific**
- [ ] **P0** Two independent MCP servers; servers don't host the LLM; HTTPS + token (cloud).
- [ ] **P0** 6 clean sub-games (Technical-Loss rerun proven); JSON-only email to
  `rmisegal+uoh26b@gmail.com`.
- [ ] **P0** Internal report JSON (§9.1); (bonus) matching inter-group JSON (§9.2) with
  `mutual_agreement: true`.
- [ ] **P1** All PRD §21 placeholders filled (team, students, repo, URLs, seed, provider).

**DoD:** Every P0 box above is checked; the repo builds, lints, tests (≥85%), and runs a full series
that emails a valid JSON-only report.
