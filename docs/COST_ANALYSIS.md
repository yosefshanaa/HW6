# LLM / API Cost Analysis

Per guidelines §11. This is a **template with the formula and placeholders**; the **MVP currently
uses heuristic agents, so live LLM cost is $0**. Real per-token numbers require an LLM run with a
provider key (`LLM_API_KEY` in `.env`) — see *External inputs* in
[`TODO.md`](TODO.md#external-inputs-needed).

---

## 1. Where tokens are spent

When the LLM-driven path is enabled (`llm.provider != none`), one LLM call is made **per agent turn**
(observe → decide). A sub-game is ≤ 25 Thief turns + ≤ 25 Cop replies = **≤ 50 turns**; a series is
**6 sub-games ≤ 300 turns**; Technical-Loss reruns add more. All calls go through the **API
Gatekeeper** (rate-limited, retried, logged), which is also the natural place to **count tokens**.

## 2. Cost model

```
per_turn_cost   = (prompt_tokens/1e6 * input_price)  + (output_tokens/1e6 * output_price)
per_series_cost = per_turn_cost * turns_per_series          # turns_per_series ≈ 50–300
```

Estimated token sizes (to be measured): a turn prompt carries the rules summary + the small partial
observation + recent messages → on the order of **~400–900 input tokens** and **~40–120 output
tokens** (a short message + a JSON action).

## 3. Estimate template (fill from a real run)

> Prices are **placeholders** — replace with the chosen provider's current published rates.

| Model | Input $/1M | Output $/1M | Input tok | Output tok | Series cost |
|---|---|---|---|---|---|
| `TODO: model-A` | `TODO` | `TODO` | `TODO` | `TODO` | `TODO` |
| `TODO: model-B` | `TODO` | `TODO` | `TODO` | `TODO` | `TODO` |

Worked example (illustrative only, **not** real prices): 300 turns × (700 in + 80 out) =
210k input + 24k output tokens per series. At a hypothetical $0.50/1M input and $1.50/1M output →
`210000/1e6*0.50 + 24000/1e6*1.50 ≈ $0.105 + $0.036 ≈ $0.14 per series`.

## 4. Optimization levers

- Keep prompts short (send **only** the legal partial observation, not full state).
- Prefer a cheap model for warm-up/smoke runs; reserve a stronger model for graded runs.
- Cache the static rules preamble; reuse across turns.
- Cap retries (gatekeeper `max_retries`) to avoid runaway cost on transient errors.
- The heuristic fallback (on invalid/unparseable LLM output) avoids paying for re-prompts that loop.

## 5. Budgeting

Track real token counts via the gatekeeper and compare to a per-series budget; alert on overrun.
Because the autonomous MVP needs no LLM, **CI and demo runs cost nothing** — only the optional
LLM-agent experiments incur spend.
