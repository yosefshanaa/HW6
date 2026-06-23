"""SDK facade — the single entry point for all business logic (PLAN §4).

GUI, CLI, reporting, and peer integrations call this class, never internal
modules directly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cop_thief.constants import ReportType
from cop_thief.domain.records import SubGameResult
from cop_thief.match.match_orchestrator import LocalMatch, MatchOutcome
from cop_thief.match.team_system import TeamSystem
from cop_thief.orchestrator.orchestrator import Orchestrator
from cop_thief.reporting.gmail_reporter import GmailReporter
from cop_thief.reporting.report_builder import (
    build_bonus_report as build_bonus_report_dict,
)
from cop_thief.reporting.report_builder import build_internal_report, validate_report
from cop_thief.shared.config import Config, load_config
from cop_thief.shared.gatekeeper import ApiGatekeeper
from cop_thief.shared.version import __version__


class CopThiefSDK:
    """Public API surface for the Cop & Thief pipeline."""

    def __init__(self, config: Config | None = None) -> None:
        self._config = config or load_config()

    @property
    def config(self) -> Config:
        """The loaded, validated configuration."""
        return self._config

    @staticmethod
    def version() -> str:
        """Return the canonical project version."""
        return __version__

    def run_series(
        self, results_dir: str | Path | None = None, seed: int | None = None
    ) -> tuple[list[SubGameResult], Path]:
        """Play a full clean series; return the results and the series directory.

        ``seed`` overrides the config seed (the live GUI passes a random one so
        each run differs); omit it for the reproducible default.
        """
        orch = Orchestrator(self._config, results_dir=results_dir, seed=seed)
        results = orch.play_series()
        return results, orch.series_dir

    def build_report(self, results: list[SubGameResult]) -> dict[str, Any]:
        """Build + validate the internal-game report dict (§9.1)."""
        report = build_internal_report(self._config, results)
        validate_report(report, ReportType.INTERNAL)
        return report

    def run_local_match(
        self, results_dir: str | Path | None = None
    ) -> tuple[MatchOutcome, Path]:
        """Play the bonus series between two local peers (Phase 12 dry-run)."""
        team_a = TeamSystem(self._config.get("match.group_1", "Team-A"), self._config)
        team_b = TeamSystem(self._config.get("match.group_2", "Team-B"), self._config)
        match = LocalMatch(self._config, team_a, team_b, results_dir=results_dir)
        return match.play_series(), match.series_dir

    def build_bonus_report(self, outcome: MatchOutcome) -> dict[str, Any]:
        """Build + validate the §9.2 inter-group report from a match outcome."""
        report = build_bonus_report_dict(
            self._bonus_meta(), outcome.results, outcome.totals_by_group
        )
        validate_report(report, ReportType.BONUS)
        return report

    def _bonus_meta(self) -> dict[str, Any]:
        """Assemble the §9.2 report metadata from config (group/url/student fields)."""
        c = self._config
        return {
            "group_1": c.get("match.group_1", "Team-A"),
            "group_2": c.get("match.group_2", "Team-B"),
            "github_repo_group_1": c.get("match.github_repo_group_1", c.get("report.github_repo")),
            "github_repo_group_2": c.get("match.github_repo_group_2", ""),
            "mcp_url_group_1_cop": c.get("match.mcp_url_group_1_cop", ""),
            "mcp_url_group_1_thief": c.get("match.mcp_url_group_1_thief", ""),
            "mcp_url_group_2_cop": c.get("match.mcp_url_group_2_cop", ""),
            "mcp_url_group_2_thief": c.get("match.mcp_url_group_2_thief", ""),
            "timezone": c.get("report.timezone", "Asia/Jerusalem"),
            "students_group_1": c.get("match.students_group_1", []),
            "students_group_2": c.get("match.students_group_2", []),
        }

    def gmail_reporter(self) -> GmailReporter:
        """Build a Gmail reporter from config (recipient, files, least-priv scope)."""
        gatekeeper = ApiGatekeeper.from_config(self._config, "gmail")
        return GmailReporter(
            self._config.get("report.recipient"),
            gatekeeper,
            credentials_file=self._config.get("report.credentials_file", "credentials.json"),
            token_file=self._config.get("report.token_file", "token.json"),
            scopes=self._config.get("report.gmail_scopes"),
        )

    def send_report(self, report: dict[str, Any], reporter: GmailReporter) -> str:
        """Send a report via the given reporter; return the message id."""
        return reporter.send(report)

    def play_and_report(
        self,
        results_dir: str | Path | None = None,
        reporter: GmailReporter | None = None,
    ) -> dict[str, Any]:
        """Run a series, build + persist the report, optionally email it."""
        results, series_dir = self.run_series(results_dir)
        report = self.build_report(results)
        (series_dir / "report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        if reporter is not None:
            self.send_report(report, reporter)
        return report
