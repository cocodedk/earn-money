"""Tests for the subzy_tool wrapper — command building and output parsing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from earn_money.recon import subzy_tool


def test_build_command_targets_file_and_concurrency() -> None:
    cmd = subzy_tool.build_command("/tmp/targets.txt", rate_limit=10)
    assert cmd[0] == "subzy"
    assert cmd[1] == "run"
    assert "--targets" in cmd
    assert cmd[cmd.index("--targets") + 1] == "/tmp/targets.txt"
    assert "--concurrency" in cmd
    assert cmd[cmd.index("--concurrency") + 1] == "10"


def test_build_command_includes_safety_flags() -> None:
    cmd = subzy_tool.build_command("/tmp/targets.txt", rate_limit=10)
    # --vuln keeps only VULNERABLE rows; --hide_fails suppresses errors.
    assert "--vuln" in cmd
    assert "--hide_fails" in cmd
    # --output /dev/stdout: subzy treats --output as a filename, not a
    # stdout marker, so we pass the proc FS path explicitly.
    assert "--output" in cmd
    assert cmd[cmd.index("--output") + 1] == "/dev/stdout"


def test_build_command_uses_custom_rate_limit() -> None:
    cmd = subzy_tool.build_command("/tmp/t.txt", rate_limit=50)
    assert cmd[cmd.index("--concurrency") + 1] == "50"


def test_build_command_rejects_non_positive_rate() -> None:
    with pytest.raises(ValueError):
        subzy_tool.build_command("/tmp/t.txt", rate_limit=0)


def test_parse_output_returns_only_vulnerable_rows(fixtures_dir: Path) -> None:
    raw = (fixtures_dir / "subzy_output.json").read_text(encoding="utf-8")
    sigs = subzy_tool.parse_output(raw, run_id="r1", observed_at="2026-05-14T10:00:00Z")
    # Fixture has 2 vulnerable, 1 not vulnerable, 1 http_error → 2 signals.
    assert len(sigs) == 2
    hosts = {s.asset for s in sigs}
    assert hosts == {"mta-sts.example.com", "old.example.com"}


def test_parse_output_signal_carries_service_and_severity(
    fixtures_dir: Path,
) -> None:
    raw = (fixtures_dir / "subzy_output.json").read_text(encoding="utf-8")
    sigs = subzy_tool.parse_output(raw, run_id="r1", observed_at="t")
    heroku = next(s for s in sigs if s.asset == "mta-sts.example.com")
    assert heroku.tool == "subzy"
    assert heroku.signal_type == "takeover_vulnerable"
    assert heroku.target == "https://mta-sts.example.com/"
    assert heroku.signature == "subzy|heroku|mta-sts.example.com"
    payload = json.loads(heroku.payload)
    assert payload["service"] == "heroku"
    assert payload["severity"] == "high"
    assert payload["status"] == "VULNERABLE"


def test_parse_output_handles_jsonl_input() -> None:
    # Some subzy versions emit one JSON object per line on stdout.
    raw = (
        '{"data":"a.example.com","status":"VULNERABLE","service":"GitHub Pages",'
        '"vulnerable":true,"https_status":404}\n'
        '{"data":"b.example.com","status":"NOT_VULNERABLE","vulnerable":false}\n'
    )
    sigs = subzy_tool.parse_output(raw, run_id="r1", observed_at="t")
    assert len(sigs) == 1
    assert sigs[0].asset == "a.example.com"


def test_parse_output_handles_wrapped_results_object() -> None:
    raw = json.dumps(
        {
            "results": [
                {"data": "x.example.com", "status": "VULNERABLE",
                 "service": "Heroku", "vulnerable": True, "https_status": 404},
            ],
        }
    )
    sigs = subzy_tool.parse_output(raw, run_id="r1", observed_at="t")
    assert len(sigs) == 1
    assert sigs[0].asset == "x.example.com"


def test_parse_output_empty_input_returns_empty_list() -> None:
    assert subzy_tool.parse_output("", run_id="r1", observed_at="t") == []


def test_parse_output_malformed_top_level_returns_empty_list() -> None:
    assert subzy_tool.parse_output(
        "not json at all", run_id="r1", observed_at="t",
    ) == []


def test_parse_output_skips_rows_missing_host() -> None:
    raw = json.dumps(
        [
            {"data": "", "vulnerable": True, "service": "Heroku"},
            {"vulnerable": True, "service": "Heroku"},
            {"data": "good.example.com", "vulnerable": True, "service": "Heroku",
             "status": "VULNERABLE", "https_status": 404},
        ]
    )
    sigs = subzy_tool.parse_output(raw, run_id="r1", observed_at="t")
    assert len(sigs) == 1
    assert sigs[0].asset == "good.example.com"
