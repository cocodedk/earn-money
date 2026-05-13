from __future__ import annotations

from pathlib import Path

import pytest

from earn_money.triage import rules


def test_load_rules_parses_yaml(tmp_path: Path) -> None:
    src = tmp_path / "triage_rules.yaml"
    src.write_text(
        "rules:\n"
        "  - name: noise.csp-script-src-wildcard\n"
        "    vuln_class: csp-script-src-wildcard\n"
        "    severity: info\n"
        "    reason: playbook-noise\n",
        encoding="utf-8",
    )
    loaded = rules.load_rules(src)
    assert len(loaded) == 1
    r = loaded[0]
    assert r.name == "noise.csp-script-src-wildcard"
    assert r.vuln_class == "csp-script-src-wildcard"
    assert r.severity == "info"
    assert r.reason == "playbook-noise"


def test_load_rules_returns_empty_when_file_missing(tmp_path: Path) -> None:
    assert rules.load_rules(tmp_path / "does-not-exist.yaml") == []


def test_load_rules_raises_on_malformed_yaml(tmp_path: Path) -> None:
    src = tmp_path / "bad.yaml"
    src.write_text("rules:\n  - name: x\n   bad-indent: y\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"malformed YAML"):
        rules.load_rules(src)


def test_load_rules_raises_on_non_dict_rule(tmp_path: Path) -> None:
    src = tmp_path / "rule_string.yaml"
    src.write_text("rules:\n  - just-a-string\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"rules\[0\] must be a mapping"):
        rules.load_rules(src)


def test_load_rules_raises_on_missing_field(tmp_path: Path) -> None:
    src = tmp_path / "incomplete.yaml"
    src.write_text(
        "rules:\n  - name: x\n    vuln_class: y\n    severity: info\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"missing required field.*reason"):
        rules.load_rules(src)


def test_match_returns_rule_on_exact_vuln_class_and_severity() -> None:
    rs = [
        rules.Rule(name="noise.csp", vuln_class="csp-script-src-wildcard",
                   severity="info", reason="playbook-noise"),
    ]
    hit = rules.match(rs, vuln_class="csp-script-src-wildcard", severity="info")
    assert hit is not None and hit.name == "noise.csp"


def test_match_returns_none_when_severity_differs() -> None:
    rs = [
        rules.Rule(name="noise.csp", vuln_class="csp-script-src-wildcard",
                   severity="info", reason="playbook-noise"),
    ]
    assert rules.match(
        rs, vuln_class="csp-script-src-wildcard", severity="high"
    ) is None


def test_match_returns_none_when_no_rule_matches() -> None:
    rs = [
        rules.Rule(name="noise.csp", vuln_class="csp-script-src-wildcard",
                   severity="info", reason="playbook-noise"),
    ]
    assert rules.match(rs, vuln_class="open-redirect", severity="info") is None
