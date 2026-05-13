# Task 1 — Rules loader

**Files:**
- Create: `src/earn_money/triage/rules.py`
- Create: `triage_rules.yaml`
- Create: `tests/triage/test_rules.py`

Builds the YAML loader and `Rule` dataclass. No matching logic yet — Task 2.

- [ ] **Step 1: Write the failing loader test**

`tests/triage/test_rules.py`:

```python
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
```

- [ ] **Step 2: Run, expect FAIL** (`pytest tests/triage/test_rules.py::test_load_rules_parses_yaml -v` — should fail with `ModuleNotFoundError`).

- [ ] **Step 3: Implement `src/earn_money/triage/rules.py`**

```python
"""Triage suppression rules: data-driven routing for known-noise nuclei
templates. Findings matching a rule are routed to _resolved/info/ with a
structured audit trail instead of reaching _queue/."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Rule:
    name: str
    vuln_class: str
    severity: str
    reason: str


def load_rules(path: Path) -> list[Rule]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    items = raw.get("rules", []) or []
    return [
        Rule(
            name=str(item["name"]),
            vuln_class=str(item["vuln_class"]),
            severity=str(item["severity"]),
            reason=str(item["reason"]),
        )
        for item in items
    ]
```

- [ ] **Step 4: Run, expect PASS** (`pytest tests/triage/test_rules.py -v`).

- [ ] **Step 5: Seed `triage_rules.yaml`** at repo root with the four playbook-noise rules listed in [`../../specs/2026-05-13-engagement-1/03-gaps.md`](../../specs/2026-05-13-engagement-1/03-gaps.md): `cookies-without-httponly`, `csp-script-src-wildcard`, `missing-cookie-samesite-strict`, `tls-version` (severity `info`, reason `playbook-noise` for the first three, `info-no-impact` for the last).

- [ ] **Step 6: `make smoke`** — must be green.

- [ ] **Step 7: Commit** as `feat(triage): rules.py YAML loader + seed file`.
