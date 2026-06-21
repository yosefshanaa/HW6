"""Assemble + validate report JSON (assignment §9.1/§9.2, PLAN §13)."""

from __future__ import annotations

from typing import Any

import jsonschema

from cop_thief.constants import ReportType
from cop_thief.domain.records import SubGameResult
from cop_thief.reporting.schemas import BONUS_SCHEMA, INTERNAL_SCHEMA


def build_internal_report(config, results: list[SubGameResult]) -> dict[str, Any]:
    """Build the §9.1 internal-game report from sub-game results."""
    return {
        "group_name": config.get("report.group_name"),
        "students": config.get("report.students", []),
        "github_repo": config.get("report.github_repo"),
        "cop_mcp_url": config.get("mcp.cop_url"),
        "thief_mcp_url": config.get("mcp.thief_url"),
        "timezone": config.get("report.timezone"),
        "sub_games": [r.as_dict() for r in results],
        "totals": {
            "cop": sum(r.cop_score for r in results),
            "thief": sum(r.thief_score for r in results),
        },
    }


def compute_bonus_claim(totals_by_group: dict[str, int]) -> dict[str, int]:
    """Higher series total → 10, other → 7, exact tie → 5 each (shared spec §5)."""
    (team_a, score_a), (team_b, score_b) = totals_by_group.items()
    if score_a == score_b:
        return {team_a: 5, team_b: 5}
    if score_a > score_b:
        return {team_a: 10, team_b: 7}
    return {team_a: 7, team_b: 10}


def build_bonus_report(
    meta: dict[str, Any],
    results: list[SubGameResult],
    totals_by_group: dict[str, int],
) -> dict[str, Any]:
    """Build the §9.2 inter-group report. ``meta`` holds team/url/student fields."""
    return {
        "report_type": ReportType.BONUS.value,
        "groups": {"group_1": meta["group_1"], "group_2": meta["group_2"]},
        "github_repo_group_1": meta["github_repo_group_1"],
        "github_repo_group_2": meta["github_repo_group_2"],
        "mcp_url_group_1_cop": meta["mcp_url_group_1_cop"],
        "mcp_url_group_1_thief": meta["mcp_url_group_1_thief"],
        "mcp_url_group_2_cop": meta["mcp_url_group_2_cop"],
        "mcp_url_group_2_thief": meta["mcp_url_group_2_thief"],
        "timezone": meta.get("timezone", "Asia/Jerusalem"),
        "students_group_1": meta.get("students_group_1", []),
        "students_group_2": meta.get("students_group_2", []),
        "sub_games": [r.as_dict() for r in results],
        "totals_by_group": totals_by_group,
        "bonus_claim": compute_bonus_claim(totals_by_group),
        "mutual_agreement": True,
    }


def validate_report(report: dict[str, Any], report_type: ReportType) -> None:
    """Validate a report against its schema; raise on mismatch."""
    schema = INTERNAL_SCHEMA if report_type is ReportType.INTERNAL else BONUS_SCHEMA
    jsonschema.validate(instance=report, schema=schema)
