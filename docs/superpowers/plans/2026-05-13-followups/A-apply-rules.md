# A — `bin/apply-rules` retroactive suppression CLI

**Problem:** `triage_rules.yaml` only suppresses *new* findings as they
flow through the engine. Pre-existing queue items (3 today) sit there
forever unless the operator clears them by hand.

**Solution:** A small CLI that walks `findings WHERE current_state =
'queued'`, applies `rules.match()`, and transitions matches to
`resolved_info` with the same audit-note format the engine uses.

**Files:**
- Create: `src/earn_money/triage/apply_rules_cli.py` (≤ 120 lines)
- Create: `bin/apply-rules` (sh wrapper)
- Create: `tests/triage/test_apply_rules_cli.py`

## TDD steps

- [ ] **1. Failing test — matches one queued finding, transitions it**

```python
def test_apply_rules_transitions_matching_queued_finding(
    tmp_repo: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    paths = engine_paths(tmp_repo)
    (paths.root / "triage_rules.yaml").write_text(
        "rules:\n  - name: noise.csp\n    vuln_class: csp\n"
        "    severity: info\n    reason: playbook-noise\n",
        encoding="utf-8",
    )
    fh = "c" * 64
    f = make_finding(finding_hash=fh, vuln_class="csp",
                     severity_hint="info",
                     notes_path=f"findings/_queue/{fh}.md")
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        findings.upsert_finding(conn, f)
    finally:
        conn.close()
    rc = apply_rules_cli.main(["--root", str(paths.root), "--program", "example"])
    assert rc == 0
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        state, = conn.execute(
            "SELECT current_state FROM findings WHERE finding_hash=?", (fh,)
        ).fetchone()
        notes = conn.execute(
            "SELECT note FROM findings_state_history WHERE finding_hash=?", (fh,)
        ).fetchall()
    finally:
        conn.close()
    assert state == "resolved_info"
    assert notes and "rule=noise.csp" in notes[0][0]
```

- [ ] **2. Failing test — non-matching queued finding untouched**

Same setup but with vuln_class="open-redirect" (no rule matches).
Assert state remains "queued" and no history rows added.

- [ ] **3. Failing test — unregistered program returns 1**

Mirrors `bin/queue`'s pattern.

- [ ] **4. Implement** `src/earn_money/triage/apply_rules_cli.py`:

  - Args: `--platform` (default `hackerone`), `--program` (required), `--root`, `--dry-run` (bool).
  - Validate scope.md exists, else stderr + return 1.
  - Load `paths.root / "triage_rules.yaml"` via `rules.load_rules`.
  - `findings.findings_in_state(conn, ..., state="queued")` to get candidates.
  - For each: `rules.match(rs, vuln_class=f.vuln_class, severity=f.severity_hint)`.
    - If match: print `would transition {hash[:8]} ({vuln_class}) → resolved_info via {rule.name}`. If not `--dry-run`, call `history.transition_state(...)` with the standard note format.
  - Print summary: `applied=<N> dry_run=<bool>`.

- [ ] **5. Create `bin/apply-rules`** mirroring `bin/queue`'s sh wrapper.
  `chmod +x`.

- [ ] **6. `make smoke`** — green.

- [ ] **7. Commit:** `feat(bin): apply-rules — retroactive suppression of queued findings`.
- [ ] **8. CodeRabbit review:** `coderabbit review --agent -t committed --base HEAD~1`. Apply valid findings in a follow-up commit.
