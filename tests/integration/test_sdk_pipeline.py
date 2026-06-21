"""End-to-end SDK pipeline test (acceptance criteria G1, G5)."""

from __future__ import annotations

import json

from cop_thief.reporting.gmail_reporter import GmailReporter
from cop_thief.sdk.sdk import CopThiefSDK
from cop_thief.shared.gatekeeper import ApiGatekeeper


def test_play_and_report_writes_and_returns_valid_report(config, tmp_path):
    sdk = CopThiefSDK(config)
    report = sdk.play_and_report(results_dir=tmp_path)
    # Report is the §9.1 shape with totals and 6 sub-games.
    assert set(report) >= {"group_name", "sub_games", "totals", "timezone"}
    assert len(report["sub_games"]) == config.get("num_games")
    # report.json persisted next to the replay logs.
    written = list(tmp_path.glob("*/report.json"))
    assert len(written) == 1
    assert json.loads(written[0].read_text(encoding="utf-8"))["totals"] == report["totals"]


def test_play_and_report_sends_via_mocked_reporter(config, tmp_path):
    sent: dict = {}
    gk = ApiGatekeeper({"requests_per_minute": 60}, sleep=lambda _s: None, clock=lambda: 0.0)
    reporter = GmailReporter(
        config.get("report.recipient"), gk,
        sender=lambda to, body: sent.update(to=to, body=body) or "msg-1",
    )
    sdk = CopThiefSDK(config)
    report = sdk.play_and_report(results_dir=tmp_path, reporter=reporter)
    assert sent["to"] == "rmisegal+uoh26b@gmail.com"
    assert json.loads(sent["body"]) == report  # JSON-only body equals the report
