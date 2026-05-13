# Task 2 — Rule matcher

**Files:**
- Modify: `src/earn_money/triage/rules.py`
- Modify: `tests/triage/test_rules.py`

Adds the matcher: given a list of rules and a (vuln_class, severity) pair,
return the first matching rule or `None`. Pure function — no DB, no IO.

- [ ] **Step 1: Write the failing match tests**

Append to `tests/triage/test_rules.py`:

```python
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
```

- [ ] **Step 2: Run, expect FAIL** (`pytest tests/triage/test_rules.py -v` — three new tests fail).

- [ ] **Step 3: Implement the matcher**

Append to `src/earn_money/triage/rules.py`:

```python
def match(
    rs: list[Rule], *, vuln_class: str, severity: str
) -> Rule | None:
    """Return the first rule matching both vuln_class and severity, else None.

    Matching is case-sensitive on both fields. Callers normalize the inputs
    (classify() already lowercases vuln_class and severity).
    """
    for r in rs:
        if r.vuln_class == vuln_class and r.severity == severity:
            return r
    return None
```

- [ ] **Step 4: Run, expect PASS** (all rule tests).

- [ ] **Step 5: `make smoke`** — must be green.

- [ ] **Step 6: Commit** as `feat(triage): rules.match() — first-rule-wins matcher`.
