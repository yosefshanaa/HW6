"""Report builder + schema tests (PRD_gmail_reporting §5)."""

from __future__ import annotations

import json

import pytest
from jsonschema.exceptions import ValidationError

from cop_thief.constants import ReportType
from cop_thief.domain.records import SubGameResult
from cop_thief.domain.roles import PlayerRole
from cop_thief.reporting.report_builder import (
    build_bonus_report,
    build_internal_report,
    compute_bonus_claim,
    validate_report,
)


def sample_results():
    return [
        SubGameResult(1, PlayerRole.COP, 8, 20, 5),
        SubGameResult(2, PlayerRole.THIEF, 25, 5, 10),
    ]


def test_internal_report_validates_and_totals(config):
    report = build_internal_report(config, sample_results())
    validate_report(report, ReportType.INTERNAL)
    assert report["totals"] == {"cop": 25, "thief": 15}
    assert report["timezone"] == "Asia/Jerusalem"
    # body must be JSON-serializable (email body is JSON only)
    assert json.loads(json.dumps(report))["sub_games"][0]["winner"] == "cop"


def test_compute_bonus_claim_cases():
    assert compute_bonus_claim({"A": 60, "B": 80}) == {"A": 7, "B": 10}
    assert compute_bonus_claim({"A": 90, "B": 30}) == {"A": 10, "B": 7}
    assert compute_bonus_claim({"A": 50, "B": 50}) == {"A": 5, "B": 5}


def test_bonus_report_validates_and_has_mutual_agreement():
    meta = {
        "group_1": "Team-A", "group_2": "Team-B",
        "github_repo_group_1": "https://github.com/a/r",
        "github_repo_group_2": "https://github.com/b/r",
        "mcp_url_group_1_cop": "https://a-cop",
        "mcp_url_group_1_thief": "https://a-thief",
        "mcp_url_group_2_cop": "https://b-cop",
        "mcp_url_group_2_thief": "https://b-thief",
    }
    report = build_bonus_report(meta, sample_results(), {"Team-A": 60, "Team-B": 80})
    validate_report(report, ReportType.BONUS)
    assert report["mutual_agreement"] is True
    assert report["bonus_claim"] == {"Team-A": 7, "Team-B": 10}


def test_invalid_report_raises(config):
    bad = build_internal_report(config, sample_results())
    del bad["totals"]
    with pytest.raises(ValidationError):
        validate_report(bad, ReportType.INTERNAL)
