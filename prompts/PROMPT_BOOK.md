# Prompt Book — HW6 Cop & Thief

A log of the significant prompts used (and planned) while building this project with an AI coding
agent, per the submission guidelines (§8.3). Prompts are paraphrased/condensed. **No API keys,
tokens, or secrets appear here** — secrets live only in the environment / `.env` (git-ignored).

> Convention: each entry notes the **goal**, the **prompt gist**, and the **expected/observed
> output**. Keep this updated as new prompts are run.

---

## 1. Documentation generation (PRD / PLAN / TODO + per-mechanism PRDs)

- **Goal:** Produce complete, professional project docs before any code.
- **Prompt gist:** "Create `docs/PRD.md`, `docs/PLAN.md`, `docs/TODO.md` and dedicated `PRD_*.md`
  for each major mechanism, based on the assignment spec, the software-submission guidelines, the
  Google OAuth guide, and `SHARED_MATCH_RULES.md`. Include the fixed game rules, MCP architecture,
  Dec-POMDP formulation, config keys, both report JSON schemas, security/least-privilege, testing
  and quality gates. Use placeholders (marked TODO) for team-specific values. Do not write code."
- **Output:** `docs/PRD.md` (21 sections), `docs/PLAN.md` (C4 + domain model + 7 ADRs),
  `docs/TODO.md` (phased checklist), and seven `docs/PRD_*.md` mechanism docs.

## 2. MVP + MCP implementation (TDD, uv-only)

- **Goal:** Implement the local working pipeline and the MCP layer from the docs.
- **Prompt gist:** "Implement phase-by-phase per `docs/TODO.md`. uv only (`uv sync`, `uv add`,
  `uv run pytest`, `uv run ruff check`). Config-driven, no hard-coded values; secrets via env;
  `.env-example`; SDK boundary; API Gatekeeper for external calls; files modular (≤150 lines);
  tests with implementation, mock external services. Build: config/version, engine
  (state/movement/barriers/scoring), partial observation, orchestration (sub-game + 6-game series),
  turn payload (message + action), logging, internal+bonus report JSON, baseline heuristic agents.
  Then MCP: Cop/Thief servers, the six tools, a client, contract tests. Gmail mocked first."
- **Output:** `src/cop_thief/**` (engine, domain, orchestrator, agents, mcp, reporting, sdk,
  shared, gui), `tests/**` (75 tests, 97% coverage), ruff clean.

## 3. Verification / release engineering

- **Goal:** Audit, finish local gaps, commit in logical chunks, push to `origin/main`.
- **Prompt gist:** "Act as a release engineer. Run `uv sync`, `uv run pytest --cov`,
  `uv run ruff check`, `uv run cop-thief`. Commit clean milestones (no secrets/caches), push after
  each. Finish only local/non-secret work (CI, prompt book, submission docs, sample evidence,
  local-testable MCP auth). Document — don't fake — external blockers (real Gmail OAuth, cloud
  hosting, partner URLs)."
- **Output:** stdout-as-pure-JSON fix (logs → stderr), CI workflow, this prompt book, submission
  docs, sample evidence, MCP bearer-token helper + tests; commits pushed to `origin/main`.

## 4. Agent turn prompt (planned — for the LLM-driven path)

When an LLM provider replaces the heuristic agents, each turn prompt should supply **only the legal
partial observation** and ask for a move plus a (possibly bluffing) message. Planned template:

```
System: You are the {role} in a 5x5 Cop-&-Thief pursuit (Dec-POMDP). Rules: {rules summary}.
        You may ONLY use the observation below; bluffing in `message` is allowed.
User:   Observation: own_cell={...}, visible_opponent={... or null}, visible_barriers=[...],
        move_number={n}, vision_radius={r}. Recent messages: [...].
        Reply with JSON: {"message": "<free text, may bluff>",
                          "action": {"type": "move|barrier", "to": [row, col]}}.
```

The referee validates `action`; the text never decides the outcome. Provider/model come from config;
calls route through the API Gatekeeper. Prompts are logged here when run.

## 5. Live Gmail setup (planned — requires the team's Google account)

- **Goal:** Produce `credentials.json` + `token.json` and send one real JSON-only report.
- **Prompt gist:** "Follow `docs/PRD_gmail_reporting.md`: enable the Gmail API, create an OAuth
  Client ID (Desktop app), External audience + add the sender as a Test user, use the least-
  privilege `gmail.send` scope (no Calendar). Download `credentials.json` (never commit). Wire
  `GmailReporter` (no injected `sender`) and run one live smoke test to `rmisegal+uoh26b@gmail.com`."
- **Blocker:** needs a real Google account + explicit approval to send live email. Not run here.

## 6. Cloud / bonus deployment (planned — requires external accounts/partner)

- **Goal:** Public HTTPS MCP servers with bearer-token auth; inter-group match.
- **Prompt gist:** "Deploy the Cop/Thief FastMCP servers to a public host (e.g., Prefect Cloud) over
  HTTPS; enable bearer-token auth (token from env, revoke after match). Exchange the four MCP URLs +
  tokens out of band with the partner team; play sub-games 1–3 (A-Cop/B-Thief) and 4–6
  (B-Cop/A-Thief); reconcile results and email identical §9.2 JSON with `mutual_agreement: true`."
- **Blocker:** needs a cloud provider + credentials and a real partner team. Not run here.

## 7. LLM-driven agents (OpenAI, hybrid LLM + heuristic guard)

- **Goal:** Make the Cop & Thief reason over the natural-language channel with a real LLM and play
  to win, without ever stalling or making an illegal move.
- **Prompt gist (build):** "Wire a provider-agnostic OpenAI responder into the `LlmClient` seam
  (key from `OPENAI_API_KEY`, never config). Add a hybrid `LlmStrategy`: one chat completion per
  turn returns JSON `{move:[r,c], barrier?, say}`; a legal-guard clamps the move to a legal cell and
  the existing heuristic is the fallback on any error/garbage/illegal move; keep the model's `say`
  (a bluff) even when the move falls back. Config-driven (`llm.provider/model`, `agents.*_strategy:
  llm`); `openai` is an optional extra; unit-test the guard with a stub client (no network)."
- **Agent system prompts (runtime — see `agents/strategy/llm_prompts.py`):**
  - **Cop:** "You are the COP… you WIN by moving onto the THIEF's exact cell. Move one king-step or
    place a BARRIER (limited budget). You see the thief only within your vision radius; the thief's
    messages MAY BE LIES. Capture fast: cut distance, herd against edges, spend barriers only when
    they trap it. You may bluff. Pick a move from the legal list. JSON only."
  - **Thief:** "You are the THIEF… you WIN by surviving the move limit. Move one king-step; no
    barriers. Stay uncapturable (distance ≥2), prefer open cells with many escape routes, avoid
    corners/edges/barriers. BLUFF about your direction to mislead the cop. Pick a move from the legal
    list. JSON only."
- **Output:** `agents/providers.py`, `agents/strategy/llm_prompts.py`, `agents/strategy/llm_strategy.py`,
  `agents/strategy/llm_factory.py`; `make_strategy(..., config=...)` builds it when strategy=`llm`;
  8 guard tests green, ruff clean.
