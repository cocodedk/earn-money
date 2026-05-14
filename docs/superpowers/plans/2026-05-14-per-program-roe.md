# Per-Program Rules-of-Engagement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Each program declares its own technique-level authority in a `roe.md` alongside `scope.md`. CLAUDE.md becomes the conservative *floor* for any field a program leaves unspecified; programs that explicitly authorize more get more.

**Architecture:** Parallel to `scope.md`. Active-probing runners (httpx, nuclei) consult the loaded RoE before sending traffic. Loader is a pure function over YAML frontmatter, same shape as `scope.read_scope`. No DB column — RoE is read-at-runtime, like scope.

**Tech Stack:** Python 3.12, `python-frontmatter`, `pyyaml`, `dataclasses`. No new runtime deps.

---

## Anti-goals (do NOT do)

- No "DoS authorized + max_rps high" runtime mode — this MVP wires the schema and a single behavioural change (rate cap override). Destructive-payload template expansion stays out until a program actually authorizes it.
- No retroactive RoE for findings already in the queue.
- No DB migration. RoE is filesystem state, like scope.

## File structure

| Path | Responsibility |
|------|----------------|
| `src/earn_money/roe.py` (new) | `RoE` dataclass, `read_roe(path)` loader, `RoEDefaults` for the floor when no roe.md exists |
| `src/earn_money/config.py` (mod) | Add `Paths.roe_file(platform, slug)` |
| `programs/hackerone/security/roe.md` (new) | Default-floor RoE for the existing program |
| `programs/hackerone/algolia/roe.md` (new) | Default-floor RoE for the existing program |
| `src/earn_money/runners/nuclei_scan.py` (mod) | Read roe.md, use `max_requests_per_second` to override the default `-rl 10` cap when set |
| `src/earn_money/runners/httpx_probe.py` (mod) | Read roe.md, log the loaded RoE at runner start (no behavioural change yet — probe is already passive enough) |
| `tests/test_roe.py` (new) | Loader + defaults + malformed-file behaviour |
| `tests/runners/test_nuclei_scan_roe.py` (new) | Runner consults roe.md for rate cap |
| `CLAUDE.md` (mod) | Add "Per-target RoE" section; reframe operational rules as floor-for-unspecified |
| `docs/superpowers/specs/2026-05-12-earn-money-design.md` (mod, optional) | One-paragraph back-reference to the RoE concept |

---

## Task 1: roe.py schema + loader (TDD)

**Files:**
- Create: `src/earn_money/roe.py`
- Test: `tests/test_roe.py`

- [ ] **Step 1.1: Write failing tests for the loader**

```python
# tests/test_roe.py
from __future__ import annotations
from pathlib import Path
import pytest
from earn_money.roe import RoE, read_roe, InvalidRoE, default_roe

def test_default_roe_is_conservative() -> None:
    d = default_roe()
    assert d.dos_authorized is False
    assert d.destructive_payloads_authorized is False
    assert d.social_engineering_authorized is False
    assert d.pii_handling == "one_redacted_screenshot"
    assert d.max_requests_per_second == 10
    assert d.authorized_test_environments == ()
    assert d.authorized_test_accounts == ()

def test_read_roe_missing_file_returns_default(tmp_path: Path) -> None:
    r = read_roe(tmp_path / "roe.md")
    assert r == default_roe()

def test_read_roe_parses_full_frontmatter(tmp_path: Path) -> None:
    (tmp_path / "roe.md").write_text(
        "---\n"
        "dos_authorized: true\n"
        "destructive_payloads_authorized: true\n"
        "social_engineering_authorized: false\n"
        "pii_handling: synthetic_data_only\n"
        "max_requests_per_second: 100\n"
        "authorized_test_environments:\n"
        "  - staging.example.com\n"
        "  - sandbox.example.com\n"
        "authorized_test_accounts:\n"
        "  - bb+test1@cocode.dk\n"
        "special_notes: |\n"
        "  Program brief authorizes load test on /api/v2/*.\n"
        "---\n"
        "free body text\n",
        encoding="utf-8",
    )
    r = read_roe(tmp_path / "roe.md")
    assert r.dos_authorized is True
    assert r.destructive_payloads_authorized is True
    assert r.pii_handling == "synthetic_data_only"
    assert r.max_requests_per_second == 100
    assert r.authorized_test_environments == ("staging.example.com", "sandbox.example.com")
    assert r.authorized_test_accounts == ("bb+test1@cocode.dk",)
    assert "load test" in r.special_notes

def test_read_roe_partial_frontmatter_fills_defaults(tmp_path: Path) -> None:
    (tmp_path / "roe.md").write_text(
        "---\nmax_requests_per_second: 50\n---\n", encoding="utf-8",
    )
    r = read_roe(tmp_path / "roe.md")
    assert r.max_requests_per_second == 50
    assert r.dos_authorized is False  # unspecified → floor

def test_read_roe_rejects_unknown_pii_handling(tmp_path: Path) -> None:
    (tmp_path / "roe.md").write_text(
        "---\npii_handling: anything_goes\n---\n", encoding="utf-8",
    )
    with pytest.raises(InvalidRoE):
        read_roe(tmp_path / "roe.md")

def test_read_roe_rejects_negative_rate(tmp_path: Path) -> None:
    (tmp_path / "roe.md").write_text(
        "---\nmax_requests_per_second: -5\n---\n", encoding="utf-8",
    )
    with pytest.raises(InvalidRoE):
        read_roe(tmp_path / "roe.md")

def test_read_roe_rejects_malformed_yaml(tmp_path: Path) -> None:
    (tmp_path / "roe.md").write_text("---\n: : :\n---\n", encoding="utf-8")
    with pytest.raises(InvalidRoE):
        read_roe(tmp_path / "roe.md")
```

- [ ] **Step 1.2: Run tests, verify they fail with ModuleNotFoundError / NameError**

`.venv/bin/pytest tests/test_roe.py -x -q`

- [ ] **Step 1.3: Implement `src/earn_money/roe.py`** — `RoE` frozen dataclass, `default_roe()`, `read_roe(path)`, `InvalidRoE`. Allowed `pii_handling` literals: `one_redacted_screenshot`, `synthetic_data_only`, `authorized_per_roe`. Validate: `max_requests_per_second` is a positive int; `dos/destructive/se` are bools; lists become tuples. Translate `yaml.YAMLError` / `KeyError` / `TypeError` into `InvalidRoE` at the source (same pattern `scope.read_scope` uses).

- [ ] **Step 1.4: Run tests, verify all pass**

- [ ] **Step 1.5: Commit**
```
git add src/earn_money/roe.py tests/test_roe.py
git commit -m "feat(roe): RoE dataclass + read_roe loader with floor defaults"
```

## Task 2: `Paths.roe_file` accessor (TDD)

**Files:**
- Modify: `src/earn_money/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 2.1: Add failing test**
```python
def test_roe_file_path(tmp_path: Path) -> None:
    p = config.Paths.from_root(tmp_path)
    assert p.roe_file("hackerone", "example") == p.program_dir("hackerone", "example") / "roe.md"
```

- [ ] **Step 2.2: Add the method to `Paths`**, one line below `scope_file`.

- [ ] **Step 2.3: Run smoke**: `make smoke`.

- [ ] **Step 2.4: Commit**
```
git commit -am "feat(config): Paths.roe_file accessor"
```

## Task 3: roe.md for existing programs

**Files:**
- Create: `programs/hackerone/security/roe.md`
- Create: `programs/hackerone/algolia/roe.md`

- [ ] **Step 3.1: Author both files with the conservative floor explicit** so the runtime behaviour is unchanged today and a future "authorize more" diff is grep-able:

```markdown
---
dos_authorized: false
destructive_payloads_authorized: false
social_engineering_authorized: false
pii_handling: one_redacted_screenshot
max_requests_per_second: 10
authorized_test_environments: []
authorized_test_accounts: []
special_notes: |
  No program brief authorizes anything above the conservative floor.
  Operator: tighten or loosen here if the program brief changes.
---

# RoE — <platform>/<slug>

This file overrides CLAUDE.md's repo-wide floor *for this program only*.
Fields left unspecified inherit the floor at read time.
```

- [ ] **Step 3.2: Commit**
```
git add programs/hackerone/{security,algolia}/roe.md
git commit -m "chore(programs): add default-floor roe.md for security + algolia"
```

## Task 4: nuclei_scan consults RoE for rate cap (TDD)

**Files:**
- Modify: `src/earn_money/runners/nuclei_scan.py`
- Modify: `src/earn_money/recon/nuclei_tool.py` (only if `build_command` needs the rate threaded through — likely it already does via a kwarg)
- Test: `tests/runners/test_nuclei_scan_roe.py`

- [ ] **Step 4.1: Write a failing test** asserting that when `roe.md` declares `max_requests_per_second: 50`, the nuclei command line carries `-rl 50` (not the default `-rl 10`).

- [ ] **Step 4.2: Thread `max_requests_per_second` from the loaded RoE through to `nuclei_tool.build_command`.** Keep the runner's default at 10 when RoE is absent or unspecified (defaults preserve current behaviour).

- [ ] **Step 4.3: Verify all existing nuclei_scan tests still pass.** Particularly `test_build_command_includes_rate_and_concurrency_caps` — it asserts `-rl 10`. With RoE at default, that still holds.

- [ ] **Step 4.4: Commit**
```
git commit -am "feat(nuclei): consult roe.md for max_requests_per_second"
```

## Task 5: httpx_probe logs loaded RoE

**Files:**
- Modify: `src/earn_money/runners/httpx_probe.py`

- [ ] **Step 5.1: Load the RoE at runner start; record the parsed values in the run's manifest.json** so the post-run audit trail shows what authority the probe operated under. No behavioural change.

- [ ] **Step 5.2: Smoke + commit**
```
git commit -am "feat(httpx): record loaded roe.md in run manifest for audit trail"
```

## Task 6: CLAUDE.md — reframe operational rules

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 6.1: Add a new section after "Three-tier program policy"**:

```markdown
### Per-program Rules of Engagement

Every `programs/<platform>/<slug>/` carries a `roe.md` alongside `scope.md`.
`roe.md` declares *technique-level* authority for that program (DoS, destructive
payloads, social engineering, PII handling, max request rate, named test
environments, named test accounts).

The operational rules below are the **floor for any field a `roe.md` does
not override**. Where a program explicitly authorizes more on its own
designated environments, the per-program RoE overrides the floor.

External-law invariants remain repo-wide regardless of RoE:

- GDPR on real third-party PII — even when a program authorizes broader
  testing, Babak-as-processor has Art. 28 obligations. RoE must specify
  `pii_handling: synthetic_data_only` or the program must supply synthetic
  test data, before any test that could touch real user records.
- `scope.md` still governs *which assets*; `roe.md` governs *technique
  on in-scope assets*.
```

- [ ] **Step 6.2: Update the "Operational rules" bullets**: change "No social engineering, no DoS, no destructive payloads — even where a program technically permits them" to read "Default-floor unless `roe.md` declares otherwise: no social engineering, no DoS, no destructive payloads." Leave the PII bullet and the egress-IP bullet unchanged (those are external-law/operational invariants).

- [ ] **Step 6.3: Commit**
```
git commit -am "docs(claude): per-program RoE overrides the floor for technique-level rules"
```

## Task 7: /simplify + /code-review

- [ ] **Step 7.1: Run /simplify against the branch diff.** Apply findings.
- [ ] **Step 7.2: Run /code-review (feature-dev:code-reviewer) against the branch.** Apply findings.
- [ ] **Step 7.3: Re-run smoke to confirm green.**

## Task 8: Surface for merge

- [ ] **Step 8.1: Push the branch.**
- [ ] **Step 8.2: Report to operator with branch name + summary.** Wait for merge instruction — do not self-merge.
