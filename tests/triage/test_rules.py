from __future__ import annotations

from pathlib import Path

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
