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

## 7b. Tuning the LLM agents to win (search-backed guard + sharper prompts)

- **Goal:** A first live LLM-vs-LLM series (`config/config.llm.yaml`, 5×5/r1, seed 1234) showed the
  Cop winning 6–0: the Thief kept fleeing into edges and stepping onto cells the Cop could capture
  next turn. Make both agents play strong moves, not merely legal ones.
- **Prompt gist:** "Replace the legal-only clamp with a light one-ply search in the guard, reusing
  the heuristic as the evaluator. Cop: always take an available capture; place a barrier only when
  the heuristic's herding gate agrees; otherwise keep the model's cell only when it ties the closest
  legal cell to the opponent. Thief: keep the model's cell only when it is a best evasion
  (uncapturable next turn = Chebyshev ≥2, then most escape routes); veto a capturable cell whenever a
  safe one exists. Always keep the model's `say` even when the move is overridden. Sharpen the system
  prompts (capture-now / stay-uncapturable tactics) and annotate each legal cell with `dist`
  (Chebyshev to opponent) and `esc` (escape routes) plus an `edge` flag so the model reasons toward
  the cell the guard would accept."
- **Output:** `heuristic.py` exposes `capture_move` / `wants_barrier` / `best_move` / `accepts_move`
  (shared `mobility`/`on_edge` moved to `base.py`); `llm_strategy.py` `_guard`; richer
  `llm_prompts.py`; +6 guard tests (14 LLM-strategy tests green). The model still drives the move
  whenever it is already a best move, and always owns the bluff channel.

## 7c. Match-ready agents: minimax move + LLM bluff (`search_llm`)

- **Goal:** Maximize strength for the inter-team match (our Thief vs their Cop, our Cop vs their
  Thief) at the agreed r2/5×5, while never emitting an illegal action (an illegal move forfeits the
  sub-game) and keeping the Cop's barrier capability. Decision made with the user: the MOVE comes
  from a deterministic search, the LLM only writes the bluff (so a flaky API can never affect the
  move or stall a turn).
- **Prompt gist:** "Add a bounded alpha-beta minimax over the *real* rules (`agents/strategy/
  search.py`): Cop maximizes (capture fast, herd, may wall its own cell within budget), Thief
  minimizes (maximize survival time). Mirror the engine exactly (thief-first, either player landing
  on the other = Cop win, barrier consumes the Cop's turn, Thief wins at `thief_moves≥max_moves`);
  only ever generate legal actions. Use search when the opponent is visible, the belief heuristic
  under fog. Wrap it in `SearchStrategy` (move) + an injected message-only LLM bluff
  (`build_message_prompt`, heuristic fallback). Register `search` and `search_llm`; add
  `config/config.match.yaml` (search_llm, r2, depth 8)."
- **Bluff prompt (message-only):** "You are the {role} at {cell}; opponent {belief}. You have
  already decided to {move/ barrier} — do NOT reveal it. Write ONE short line (<12 words) that bluffs:
  name a direction/cell you are NOT going to. JSON only: {\"say\":\"...\"}."
- **Result (deterministic eval, r2, 12 seeds × 6 = 72 sub-games each):** heuristic-vs-heuristic =
  Cop 72/0 (r2 is ~100% Cop). Our **search Cop** captures every game in ~3.8 moves (vs heuristic's
  8.0). Our **search Thief survives a heuristic Cop 57%** of games (heuristic Thief: 0%). Search vs
  search = Cop 72/0 (a perfect Cop wins at r2). So the match hinges on our Thief out-surviving their
  Cop — the edge we maximized. `search.py` + `search_strategy.py` + 6 search tests (incl. an
  "always legal" property test over random states); 160 tests green, ruff clean.
