"""Gmail reporter tests — fully mocked, no real send (PRD_gmail_reporting §5)."""

from __future__ import annotations

import json

from cop_thief.reporting.gmail_reporter import GmailReporter
from cop_thief.shared.gatekeeper import ApiGatekeeper


def make_gatekeeper():
    return ApiGatekeeper({"requests_per_minute": 60}, sleep=lambda _s: None, clock=lambda: 0.0)


def test_send_uses_json_only_body_and_recipient():
    captured: dict = {}

    def fake_sender(to: str, body: str) -> str:
        captured["to"] = to
        captured["body"] = body
        return "msg-123"

    report = {"group_name": "Team", "totals": {"cop": 25, "thief": 15}}
    reporter = GmailReporter(
        "rmisegal+uoh26b@gmail.com", make_gatekeeper(), sender=fake_sender
    )
    message_id = reporter.send(report)

    assert message_id == "msg-123"
    assert captured["to"] == "rmisegal+uoh26b@gmail.com"
    # Body must parse as JSON and equal the report exactly (JSON only, no extra text).
    assert json.loads(captured["body"]) == report
    assert captured["body"] == json.dumps(report)


def test_default_scope_is_least_privilege_send_only():
    reporter = GmailReporter("x@example.com", make_gatekeeper())
    assert reporter.scopes == ["https://www.googleapis.com/auth/gmail.send"]
    assert "https://www.googleapis.com/auth/calendar" not in reporter.scopes
