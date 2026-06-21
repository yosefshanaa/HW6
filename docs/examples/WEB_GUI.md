# Browser GUI evidence

The browser GUI (`uv run cop-thief-web-gui`) renders a **self-contained, local** HTML page — no
network, no CDN, no external services. Data is embedded directly in the page as JSON.

## Curated sample

[`sample_web_gui.html`](sample_web_gui.html) — a real replay of one completed sub-game (Cop wins).
Open it in any browser (double-click, or `file://` path). It is regenerated with:

```bash
uv run cop-thief --results-dir results
uv run cop-thief-web-gui --replay results/<ts>/sub_game_1.jsonl \
    --no-open --output docs/examples/sample_web_gui.html
```

## What the page shows

```
 Cop & Thief — Web GUI
 [ Sub-game ▼ ]  Move [====|----]  3 / 5   [▶ Play]
 Sub-game 1 — winner cop (cop 20 / thief 5)

 ┌── True board ──┐   ┌── Fog-of-war (cop) ──┐   ┌── Turn ──────────────┐
 │ . . . . .      │   │ C . . ? ?            │   │ role: cop            │
 │ . . . . .      │   │ . . . ? ?            │   │ action: {move,[1,1]} │
 │ . . C . .      │   │ ? ? ? ? ?            │   │ message: closing in  │
 │ . . . T .      │   │ ? ? ? ? ?            │   │                      │
 │ . . . . .      │   │ ? ? ? ? ?            │   │ Series totals        │
 └────────────────┘   └─────────────────────┘   │ cop 105 / thief 35   │
 Message / action log
 [0 thief] slipping toward [0,0]  →  {"type":"move","to":[1,1]}
 [0 cop]   closing in toward [3,1] →  {"type":"move","to":[1,1]}  ...
```

- **True board** — full state (C=cop, T=thief, ▦=barrier).
- **Fog-of-war** — the acting agent's partial view (`?` = beyond its vision radius).
- **Sub-game selector** + **move slider** + **▶ Play** to step/animate the series.
- **Winner / per-sub-game scores** and **series totals**.
- **Message/action log** (the natural-language `message`s, including the Thief's bluffs).

## Screenshot

To capture a PNG for the report: open `sample_web_gui.html` (or a live run) in a browser and use the
OS screenshot tool; save it under `assets/`. (No image is committed here to keep the repo light.)
