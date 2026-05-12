from __future__ import annotations

import json
from pathlib import Path

import pytest

from earn_money.recon import nuclei_tool


def test_approved_template_dirs_constant_locked() -> None:
    assert frozenset({
        "http/cves",
        "http/misconfiguration",
    }) == nuclei_tool.APPROVED_TEMPLATE_DIRS


def test_build_command_includes_safety_flags() -> None:
    cmd = nuclei_tool.build_command(
        ["https://api.example.com/"],
        template_dirs=("http/cves", "http/misconfiguration"),
    )
    assert "-disable-redirects" in cmd
    assert "-jsonl" in cmd
    assert "-silent" in cmd
    assert "-no-interactsh" in cmd
    assert "-disable-update-check" in cmd
    assert "-t" in cmd
    t_indices = [i for i, a in enumerate(cmd) if a == "-t"]
    t_values = [cmd[i + 1] for i in t_indices]
    assert set(t_values) == {"http/cves", "http/misconfiguration"}


def test_build_command_includes_rate_and_concurrency_caps() -> None:
    cmd = nuclei_tool.build_command(
        ["https://api.example.com/"],
        template_dirs=("http/cves",),
    )
    assert "-rl" in cmd
    assert cmd[cmd.index("-rl") + 1] == "10"
    assert "-c" in cmd
    assert cmd[cmd.index("-c") + 1] == "10"
    assert "-bs" in cmd
    assert cmd[cmd.index("-bs") + 1] == "10"
    assert "-stats-interval" in cmd
    assert cmd[cmd.index("-stats-interval") + 1] == "60"


def test_build_command_passes_targets_via_u() -> None:
    cmd = nuclei_tool.build_command(
        ["https://api.example.com/", "https://www.example.com/"],
        template_dirs=("http/cves",),
    )
    assert "-u" in cmd
    u_index = cmd.index("-u")
    assert cmd[u_index + 1] == "https://api.example.com/,https://www.example.com/"


def test_build_command_rejects_unapproved_template_dir() -> None:
    with pytest.raises(nuclei_tool.UnsafeTemplateProfile):
        nuclei_tool.build_command(
            ["https://api.example.com/"],
            template_dirs=("cves", "dos"),
        )


def test_build_command_empty_targets_raises() -> None:
    with pytest.raises(ValueError):
        nuclei_tool.build_command([], template_dirs=("http/cves",))


def test_parse_jsonl_returns_signals(fixtures_dir: Path) -> None:
    raw = (fixtures_dir / "nuclei_output.jsonl").read_text(encoding="utf-8")
    signals = nuclei_tool.parse_jsonl(raw, run_id="r1", observed_at="2026-05-12T02:30:00Z")
    assert len(signals) == 3
    cve = next(s for s in signals if "CVE-2023-1234" in s.signature)
    assert cve.signal_type == "template_match"
    assert cve.asset == "api.example.com"
    assert cve.target == "https://api.example.com/search?q=foo"
    assert cve.signature.startswith("CVE-2023-1234|primary|")


def test_parse_jsonl_skips_malformed_lines(fixtures_dir: Path) -> None:
    raw = "not json\n" + (fixtures_dir / "nuclei_output.jsonl").read_text(encoding="utf-8")
    signals = nuclei_tool.parse_jsonl(raw, run_id="r1", observed_at="t")
    assert len(signals) == 3


def test_parse_jsonl_payload_carries_severity_and_template(fixtures_dir: Path) -> None:
    raw = (fixtures_dir / "nuclei_output.jsonl").read_text(encoding="utf-8")
    signals = nuclei_tool.parse_jsonl(raw, run_id="r1", observed_at="t")
    cve = next(s for s in signals if "CVE-2023-1234" in s.signature)
    payload = json.loads(cve.payload)
    assert payload["template_id"] == "CVE-2023-1234"
    assert payload["severity"] == "high"
    assert payload["matched_at"] == "https://api.example.com/search?q=foo"
