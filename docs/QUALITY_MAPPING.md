# ISO/IEC 25010 Quality Mapping

Per guidelines §13. Maps the eight product-quality characteristics to **concrete evidence** in this
repository. Status: ✅ met locally · ◐ partial / external-gated.

| Characteristic | How it is addressed | Evidence | Status |
|---|---|---|---|
| **Functional suitability** | All MUST rules implemented (turns, 8-dir moves, barriers, capture, 25-move cap, scoring, 6-game series) and the autonomous pipeline | `engine/`, `orchestrator/`; `tests/unit/test_engine.py`, `tests/integration/test_series.py`; `uv run cop-thief` | ✅ |
| **Performance efficiency** | Pure O(1)-per-turn engine; gatekeeper caps ~30 req/min/direction; per-turn timeout configurable | `engine/referee.py`, `shared/gatekeeper.py`, `config/rate_limits.json` | ✅ |
| **Compatibility** | Stable JSON contracts (turn payload, observation, §9.1/§9.2 reports) for two independently-built engines; cross-platform (`uv`) | `mcp/contracts.py`, `reporting/schemas.py`; `tests/integration/test_mcp_contract.py` | ✅ |
| **Usability** | One-command run; README user manual; text GUI + replay; clear errors; logs on stderr keep stdout pure JSON | `README.md`, `main.py`, `gui/app.py` | ✅ |
| **Reliability** | Technical-Loss void-and-rerun to 6 clean sub-games; gatekeeper retries; safe-move fallback (never stalls); ≥85% coverage | `orchestrator/technical_loss.py`, `orchestrator/turn_loop.py`; `tests/integration/test_series.py` (97% cov) | ✅ |
| **Security** | Secrets only via env + `.env-example`; `.gitignore` covers secrets; least-privilege `gmail.send`; constant-time bearer-token check; no secrets tracked | `.gitignore`, `.env-example`, `reporting/gmail_reporter.py`, `mcp/auth.py`; `tests/unit/test_auth.py`. ◐ HTTPS + live token enforcement is the cloud stage | ◐ |
| **Maintainability** | SDK boundary; modular files ≤150 lines; OOP/no-duplication (Template-Method `Strategy`, shared MCP tools/builder); ADRs; Ruff-clean | `sdk/sdk.py`, `agents/strategy/base.py`, `mcp/{tools,server_app}.py`; `docs/PLAN.md` §23 | ✅ |
| **Portability** | `uv`-managed env + `uv.lock`; config-driven (grid/radius/scoring/urls); CI on Ubuntu; optional extras (`mcp`, `gmail`). ◐ cloud deploy external | `pyproject.toml`, `.github/workflows/ci.yml`, `config/config.yaml` | ◐ |

**Sub-characteristics highlight (Security):** confidentiality (no secrets in code/repo),
integrity (referee is the single authoritative writer; action — not text — decides outcomes),
authenticity (bearer-token check). **Reliability:** maturity + fault tolerance + recoverability via
Technical-Loss rerun. **Maintainability:** modularity, reusability, analysability, testability,
modifiability (config-first).

> The two ◐ rows are gated only on external cloud/account inputs
> ([`TODO.md` §External Inputs Needed](TODO.md#external-inputs-needed)); the supporting code paths
> exist and are tested with mocks.
