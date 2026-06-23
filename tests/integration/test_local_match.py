"""Local inter-group match dry-run tests (PRD_bonus_match §5, Phase 12)."""

from __future__ import annotations

import json

import jsonschema

from cop_thief.constants import ReportType
from cop_thief.domain.records import SubGameResult
from cop_thief.domain.roles import PlayerRole
from cop_thief.match.match_orchestrator import LocalMatch
from cop_thief.match.team_system import TeamSystem
from cop_thief.mcp.contracts import TURN_PAYLOAD_SCHEMA
from cop_thief.reporting.report_builder import validate_report
from cop_thief.sdk.sdk import CopThiefSDK


def _teams(config):
    return TeamSystem("Team-A", config), TeamSystem("Team-B", config)


def test_full_series_runs_and_scores(config, tmp_path):
    a, b = _teams(config)
    outcome = LocalMatch(config, a, b, results_dir=tmp_path).play_series()
    assert len(outcome.results) == config.get("num_games")
    for r in outcome.results:
        assert r.winner in (PlayerRole.COP, PlayerRole.THIEF)
        assert r.moves_played <= config.get("max_moves")
        expected = (20, 5) if r.winner is PlayerRole.COP else (5, 10)
        assert (r.cop_score, r.thief_score) == expected


def test_role_split_swaps_at_halfway(config, tmp_path):
    a, b = _teams(config)
    match = LocalMatch(config, a, b, results_dir=tmp_path)
    assert match.roles(1) == (a, b)
    assert match.roles(match.half) == (a, b)
    assert match.roles(match.half + 1) == (b, a)
    assert match.roles(config.get("num_games")) == (b, a)


def test_team_totals_aggregate_by_team_with_role_swap(config, tmp_path):
    """Role scores roll up to the correct TEAM, accounting for the 1-3 / 4-6 swap:
    Team-A Cop in 1-3, Team-B Cop in 4-6 (Cop win 20/5, Thief win 5/10)."""
    a, b = _teams(config)  # "Team-A", "Team-B"
    match = LocalMatch(config, a, b, results_dir=tmp_path)
    results = [
        SubGameResult(1, PlayerRole.COP, 3, 20, 5),    # A Cop wins  -> A 20, B 5
        SubGameResult(2, PlayerRole.THIEF, 25, 5, 10),  # A Cop loses -> A 5,  B 10
        SubGameResult(3, PlayerRole.COP, 3, 20, 5),    # A Cop wins  -> A 20, B 5
        SubGameResult(4, PlayerRole.THIEF, 25, 5, 10),  # B Cop loses -> B 5,  A 10
        SubGameResult(5, PlayerRole.COP, 3, 20, 5),    # B Cop wins  -> B 20, A 5
        SubGameResult(6, PlayerRole.THIEF, 25, 5, 10),  # B Cop loses -> B 5,  A 10
    ]
    assert match._totals(results) == {"Team-A": 70, "Team-B": 50}


def test_bonus_report_sub_games_carry_team_attribution(config, tmp_path):
    sdk = CopThiefSDK(config)
    outcome, _ = sdk.run_local_match(results_dir=tmp_path)
    report = sdk.build_bonus_report(outcome)
    group_a = config.get("match.group_1", "Team-A")
    group_b = config.get("match.group_2", "Team-B")
    sg = report["sub_games"]
    assert sg[0]["cop_group"] == group_a and sg[0]["thief_group"] == group_b   # 1-3: A Cop
    assert sg[-1]["cop_group"] == group_b and sg[-1]["thief_group"] == group_a  # 4-6: B Cop
    for row in sg:
        assert row["winner_group"] in (row["cop_group"], row["thief_group"])


def test_cli_prints_human_summary_to_stderr(tmp_path, monkeypatch, capsys):
    from cop_thief.match import cli

    monkeypatch.setattr("sys.argv", ["cop-thief-match", "--results-dir", str(tmp_path)])
    cli.main()
    captured = capsys.readouterr()
    assert "Two-team bonus dry-run" in captured.err
    assert "sub-game 1:" in captured.err and "Cop=" in captured.err and "Thief=" in captured.err
    assert "team totals:" in captured.err
    # stdout still carries the machine-readable §9.2 JSON as its last line
    json.loads(captured.out.strip().splitlines()[-1])


def test_two_engines_reconcile_cleanly(config, tmp_path):
    a, b = _teams(config)
    outcome = LocalMatch(config, a, b, results_dir=tmp_path).play_series()
    assert outcome.flags == []


def test_submitted_envelopes_match_mcp_schema(config, tmp_path):
    a, b = _teams(config)
    match = LocalMatch(config, a, b, results_dir=tmp_path)
    match.play_series()
    logs = sorted(match.series_dir.glob("sub_game_*.jsonl"))
    assert logs
    for line in logs[0].read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        envelope = {
            "sub_game": rec["sub_game"],
            "move_number": rec["move_number"],
            "role": rec["role"],
            "message": rec["message"],
            "action": rec["action"],
        }
        jsonschema.validate(instance=envelope, schema=TURN_PAYLOAD_SCHEMA)


def test_bonus_report_validates_with_mutual_agreement(config, tmp_path):
    sdk = CopThiefSDK(config)
    outcome, _series_dir = sdk.run_local_match(results_dir=tmp_path)
    report = sdk.build_bonus_report(outcome)
    validate_report(report, ReportType.BONUS)
    assert report["mutual_agreement"] is True
    assert set(report["totals_by_group"]) == set(report["bonus_claim"])
    # Bonus claim is 10+7 for a decisive series or 5+5 for an exact tie.
    assert sum(report["bonus_claim"].values()) in (17, 10)


def test_cli_prints_valid_bonus_report(tmp_path, monkeypatch, capsys):
    from cop_thief.match import cli

    monkeypatch.setattr("sys.argv", ["cop-thief-match", "--results-dir", str(tmp_path)])
    cli.main()
    report = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    validate_report(report, ReportType.BONUS)
    assert report["report_type"] == "bonus_game"


def test_technical_loss_voids_and_reruns(config, tmp_path):
    a, b = _teams(config)
    match = LocalMatch(
        config, a, b, results_dir=tmp_path,
        failure_injector=lambda index, attempt: index == 1 and attempt == 1,
    )
    outcome = match.play_series()
    assert len(outcome.results) == config.get("num_games")
