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
from cop_thief.orchestrator.orchestrator import Orchestrator
from cop_thief.reporting.gmail_reporter import GmailReporter
from cop_thief.reporting.report_builder import build_internal_report, validate_report
from cop_thief.shared.config import Config, load_config
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

    def run_series(self, results_dir: str | Path | None = None) -> tuple[list[SubGameResult], Path]:
        """Play a full clean series; return the results and the series directory."""
        orch = Orchestrator(self._config, results_dir=results_dir)
        results = orch.play_series()
        return results, orch.series_dir

    def build_report(self, results: list[SubGameResult]) -> dict[str, Any]:
        """Build + validate the internal-game report dict (§9.1)."""
        report = build_internal_report(self._config, results)
        validate_report(report, ReportType.INTERNAL)
        return report

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
