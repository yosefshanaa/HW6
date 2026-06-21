"""Local browser GUI entry point — ``uv run cop-thief-web-gui``.

Renders a fresh local series (or a replay JSONL file / series directory) as a
self-contained HTML page and opens it in the default browser. Local-only: no
network, Gmail, cloud, LLM, or partner URLs.
"""

from __future__ import annotations

import argparse
import json
import webbrowser
from pathlib import Path

from cop_thief.gui.render import build_html, group_rounds, turn_view
from cop_thief.sdk.sdk import CopThiefSDK
from cop_thief.shared.replay import ReplayStore


def _sub_view(index, winner, cop_score, thief_score, moves, records, grid) -> dict:
    turns = [turn_view(r, grid) for r in records]
    return {
        "index": index, "winner": winner, "cop_score": cop_score,
        "thief_score": thief_score, "moves_played": moves,
        "rounds": group_rounds(turns),
    }


def run_live(sdk: CopThiefSDK, grid: list[int]) -> dict:
    """Play a fresh local series and build the view-model with scores."""
    results, series_dir = sdk.run_series()
    report = sdk.build_report(results)
    subs = []
    for r in results:
        records = ReplayStore(series_dir / f"sub_game_{r.index}.jsonl").load()
        subs.append(_sub_view(r.index, r.winner.value, r.cop_score, r.thief_score,
                              r.moves_played, records, grid))
    return {"grid_size": grid, "totals": report["totals"], "sub_games": subs}


def load_replay(path: str, grid: list[int], sdk: CopThiefSDK) -> dict:
    """Build a view-model from a series directory or a single sub-game JSONL."""
    p = Path(path)
    return _replay_dir(p, grid) if p.is_dir() else _replay_file(p, grid, sdk)


def _replay_dir(p: Path, grid: list[int]) -> dict:
    report = json.loads((p / "report.json").read_text(encoding="utf-8"))
    subs = [
        _sub_view(sg["index"], sg["winner"], sg["cop_score"], sg["thief_score"],
                  sg["moves_played"], ReplayStore(p / f"sub_game_{sg['index']}.jsonl").load(), grid)
        for sg in report["sub_games"]
    ]
    return {"grid_size": grid, "totals": report["totals"], "sub_games": subs}


def _replay_file(p: Path, grid: list[int], sdk: CopThiefSDK) -> dict:
    records = ReplayStore(p).load()
    status = records[-1]["resulting_state"]["status"] if records else "ongoing"
    sc = sdk.config.get("scoring")
    if status == "cop_win":
        winner, cop, thief = "cop", sc["cop_win"], sc["thief_loss"]
    elif status == "thief_win":
        winner, cop, thief = "thief", sc["cop_loss"], sc["thief_win"]
    else:
        winner, cop, thief = "in progress", 0, 0
    idx = records[0]["sub_game"] if records else 1
    moves = records[-1]["move_number"] if records else 0
    sub = _sub_view(idx, winner, cop, thief, moves, records, grid)
    return {"grid_size": grid, "totals": {"cop": cop, "thief": thief}, "sub_games": [sub]}


def main() -> None:
    """Build the HTML page and open it in a browser (or just write it)."""
    parser = argparse.ArgumentParser(description="Cop & Thief — local browser GUI.")
    parser.add_argument("--replay", default=None, help="JSONL file or a series directory")
    parser.add_argument("--output", default=None, help="HTML output path")
    parser.add_argument("--no-open", action="store_true", help="write HTML without opening a browser")
    args = parser.parse_args()

    sdk = CopThiefSDK()
    grid = sdk.config.get("grid_size")
    view = load_replay(args.replay, grid, sdk) if args.replay else run_live(sdk, grid)

    default = Path(sdk.config.get("logging.results_dir", "results")) / "web_gui.html"
    out = Path(args.output or default)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_html(view), encoding="utf-8")
    print(f"Web GUI written to {out}")
    if not args.no_open and webbrowser.open(out.resolve().as_uri()):
        print("Opened in your browser.")
    else:
        print(f"Open this file in a browser: {out.resolve()}")


if __name__ == "__main__":
    main()
