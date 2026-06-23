# Submission Report — HW6: Dual AI Agent Race via MCP (Cop & Thief)

**Version:** 1.00 · **Repo:** https://github.com/yosefshanaa/HW6 · **Date:** 2026-06-23

A single-page overview tying the deliverables together for grading. Detailed docs are linked
throughout.

---

## 1. What this is

Two autonomous AI agents — a **Cop** and a **Thief** — play a turn-based, **partially observable**
(Dec-POMDP) pursuit game on a configurable grid, each fronted by its **own MCP server**, coordinated
by an orchestrator that drives the turn loop, enforces rules via a single referee, logs every turn,
and emails a **JSON-only** report. The graded core is **orchestration & systems engineering**, not
the game outcome.

## 2. What is implemented and verified locally

- **Config-driven game engine** (rules, 8-dir movement, barriers, capture, 25-move cap, scoring) —
  no hard-coded values. [`PRD_game_engine.md`](PRD_game_engine.md)
- **Partial observability** (Chebyshev vision radius; out-of-radius start placement).
  [`PRD_partial_observability.md`](PRD_partial_observability.md)
- **Baseline heuristic agents** (run with **no LLM/credentials**); optional tabular Q-Learning core.
  [`PRD_agent_strategy.md`](PRD_agent_strategy.md)
- **Orchestrator**: 6-sub-game series, thief-first turns, **Technical-Loss void-and-rerun**, safe-move
  fallback (never stalls).
- **NL channel**: `message` (may bluff) + authoritative `action`; the referee decides on the action.
- **MCP layer**: two FastMCP servers, six tools, schema-validated payloads, in-process client +
  contract tests. Servers **do not host the LLM**. [`PRD_mcp_servers.md`](PRD_mcp_servers.md)
- **Reporting**: internal (§9.1) + bonus (§9.2) JSON builders; **mockable** Gmail reporter with a
  **JSON-only** body and least-privilege `gmail.send` scope. [`PRD_gmail_reporting.md`](PRD_gmail_reporting.md)
- **Cross-cutting**: SDK facade, API Gatekeeper, structured JSONL logging + replay, terminal +
  **browser** GUIs (loopback server with a live **Play Again**), bearer-token auth check, CI workflow.
- **Inter-group bonus dry-run** (`cop-thief-match`): two-team, role-swapping series on the loopback
  transport with mirror-and-flag reconciliation; emits the §9.2 bonus JSON. Real partner endpoints
  remain external.

## 3. How to run

```bash
uv sync
uv run cop-thief                 # full autonomous series → JSON-only report on stdout
uv run cop-thief-web-gui         # browser GUI (loopback) with a live Play Again button
uv run cop-thief-match           # two-team bonus dry-run (loopback) → §9.2 JSON on stdout
uv run cop-thief-gui --replay results/<ts>/sub_game_1.jsonl
uv run python notebooks/parameter_sweep.py     # local parameter sweep
uv sync --extra mcp && uv run cop-thief-cop-server   # MCP server (localhost)
```

See [`README.md`](../README.md) for the full manual.

## 4. Quality evidence

| Gate | Result |
|---|---|
| Tests | **131 passed** (`uv run pytest`) |
| Coverage | **98%** (target ≥85%, `fail_under=85`) |
| Lint | **0** violations (`uv run ruff check`) |
| File size | all ≤ **150** code lines (largest 147) |
| Secrets | none tracked; `.env-example` only; `.gitignore` covers secrets/caches |
| CI | `.github/workflows/ci.yml` (uv sync → ruff → pytest --cov) |

Architecture/ADRs: [`PLAN.md`](PLAN.md). Requirements: [`PRD.md`](PRD.md). Task status:
[`TODO.md`](TODO.md). ISO/IEC 25010: [`QUALITY_MAPPING.md`](QUALITY_MAPPING.md). Prompts:
[`../prompts/PROMPT_BOOK.md`](../prompts/PROMPT_BOOK.md).

## 5. Report schemas

- **Internal (§9.1):** sample at [`examples/sample_report.json`](examples/sample_report.json).
- **Bonus (§9.2):** built by `reporting/report_builder.build_bonus_report` with
  `mutual_agreement: true` (validated by `tests/unit/test_report.py`).

## 6. Research & cost

- Parameter sensitivity (real local runs): [`EXPERIMENTS.md`](EXPERIMENTS.md) — board size dominates;
  vision radius is non-monotonic due to the start-distance constraint.
- LLM token cost model + optimization: [`COST_ANALYSIS.md`](COST_ANALYSIS.md) (MVP cost = $0; needs an
  LLM key for real numbers).

## 7. Status & what remains

**Done locally:** Phases 1–10, 13–14, CI, prompt book, analysis docs (see
[`TODO.md`](TODO.md) status snapshot).

**Gated on external inputs** (documented, not faked): live Gmail OAuth send, cloud HTTPS deploy +
live bearer enforcement, partner bonus match, real cloud MCP URLs, team/student details, LLM
provider/model. Full list:
[`TODO.md` §External Inputs Needed](TODO.md#external-inputs-needed).
