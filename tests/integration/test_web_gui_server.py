"""Live browser-GUI server tests (loopback only, no real series run)."""

from __future__ import annotations

import json
import threading
import urllib.request

from cop_thief.gui.web_app import GuiServer


def _get(url: str) -> str:
    return urllib.request.urlopen(url, timeout=5).read().decode("utf-8")


def _post(url: str) -> dict:
    req = urllib.request.Request(url, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=5).read())


def test_new_series_endpoint_returns_and_updates_view():
    """GET / serves the current page; POST /api/new-series runs the (fake) series
    factory, returns the fresh view-model, and updates the served state."""
    counter = {"i": 0}

    def fake_new_series() -> dict:
        counter["i"] += 1
        return {"grid_size": [5, 5], "totals": {"cop": counter["i"], "thief": 0},
                "sub_games": []}

    first = {"grid_size": [5, 5], "totals": {"cop": 0, "thief": 0}, "sub_games": []}
    server = GuiServer(("127.0.0.1", 0), first, fake_new_series)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        html = _get(base + "/")
        assert 'id="again"' in html              # Play Again button is served
        assert json.dumps(first) in html         # initial view embedded

        v1 = _post(base + "/api/new-series")
        v2 = _post(base + "/api/new-series")
        assert v1["totals"]["cop"] == 1
        assert v2["totals"]["cop"] == 2          # repeated calls -> fresh view each time
        assert v1 != v2
        assert json.dumps(v2) in _get(base + "/")  # GET reflects the latest series
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
