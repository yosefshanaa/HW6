# Example artifacts

Small, curated, **non-secret** evidence from a local run of the autonomous pipeline
(`uv run cop-thief`). Regenerate at any time — runs are reproducible from the config `seed`.

- **`sample_report.json`** — a full §9.1 internal-game report (the JSON-only body the Gmail
  reporter would email). Team/URL fields are intentionally left as `TODO` placeholders;
  `github_repo` is set.
- **`sample_sub_game_excerpt.jsonl`** — the first six timestamped turn records of sub-game 1
  (one JSON object per line): observation, natural-language `message` (note the Thief's **bluff**),
  committed `action`, validation, and resulting board state.
- **`sample_web_gui.html`** + **[`WEB_GUI.md`](WEB_GUI.md)** — a self-contained browser-GUI replay
  of one completed sub-game, plus how to launch/screenshot it (`uv run cop-thief-web-gui`).

Reproduce:

```bash
uv run cop-thief --results-dir results
# results/<timestamp>/report.json  +  results/<timestamp>/sub_game_*.jsonl
```

Replay a sub-game as a text board:

```bash
uv run cop-thief-gui --replay results/<timestamp>/sub_game_1.jsonl
```
