"""Local browser GUI entry point — ``uv run cop-thief-web-gui``.

By default starts a tiny **loopback-only** HTTP server (Python stdlib, no extra
dependency): it serves the GUI and a ``Play Again`` button that runs a brand-new
local series. ``--output`` instead writes a self-contained static HTML file (for
screenshots / replay evidence) and exits. Local-only: no network exposure,
Gmail, cloud, LLM, or partner URLs.
"""

from __future__ import annotations

import argparse
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


class GuiServer(ThreadingHTTPServer):
    """Loopback-only GUI server: holds the current view-model + a series factory."""

    daemon_threads = True

    def __init__(self, address, view: dict, new_series) -> None:
        super().__init__(address, _GuiHandler)
        self.view = view
        self.new_series = new_series  # callable() -> fresh view-model dict


class _GuiHandler(BaseHTTPRequestHandler):
    """GET / serves the page; POST /api/new-series runs a fresh series."""

    def log_message(self, *_args) -> None:  # keep stdout clean
        pass

    def do_GET(self) -> None:
        if self.path != "/":
            self.send_error(404)
            return
        self._send(200, "text/html; charset=utf-8", build_html(self.server.view, live=True))

    def do_POST(self) -> None:
        if self.path != "/api/new-series":
            self.send_error(404)
            return
        self.server.view = self.server.new_series()
        self._send(200, "application/json", json.dumps(self.server.view))

    def _send(self, code: int, ctype: str, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _open(uri: str, no_open: bool) -> None:
    if not no_open and webbrowser.open(uri):
        print("Opened in your browser.")
    else:
        print(f"Open this in a browser: {uri}")


def main() -> None:
    """Start the live GUI server, or write a static HTML file with ``--output``."""
    parser = argparse.ArgumentParser(description="Cop & Thief — local browser GUI.")
    parser.add_argument("--replay", default=None, help="JSONL file or a series directory")
    parser.add_argument("--output", default=None, help="write a static HTML file and exit")
    parser.add_argument("--no-open", action="store_true", help="do not open a browser")
    parser.add_argument("--port", type=int, default=0, help="live server port (0 = auto-select)")
    args = parser.parse_args()

    sdk = CopThiefSDK()
    grid = sdk.config.get("grid_size")
    view = load_replay(args.replay, grid, sdk) if args.replay else run_live(sdk, grid)

    if args.output:  # static export — self-contained file, Play Again hidden
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(build_html(view), encoding="utf-8")
        print(f"Static GUI written to {out}")
        _open(out.resolve().as_uri(), args.no_open)
        return

    server = GuiServer(("127.0.0.1", args.port), view, lambda: run_live(sdk, grid))
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Live GUI at {url}  —  Play Again runs a new series; Ctrl+C to stop.")
    _open(url, args.no_open)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
