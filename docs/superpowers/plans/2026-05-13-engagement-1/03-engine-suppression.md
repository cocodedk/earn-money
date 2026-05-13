# Task 3 — Engine suppression wiring

**Files:**
- Modify: `src/earn_money/triage/engine.py`
- Modify: `tests/triage/test_engine.py`

For every new finding, consult `rules.match()`. On match, route to
`_resolved/info/`, write an audit row, and emit the structured `note`.

## Audit-note format

`rule=<rule.name> template=<vuln_class> version=<ver> reason=<rule.reason>`

`<ver>` reads from `payload.info.version` if the nuclei payload exposes
it (real nuclei rarely does), else `unknown`. Both forms are explicit.

- [ ] **Step 1: Write the failing engine test**

Append to `tests/triage/test_engine.py` (mirrors the seeding pattern of
`test_triages_one_nuclei_run_and_writes_queue_file`, swapping in a payload
that matches a rule):

```python
def test_engine_routes_suppressed_finding_to_resolved_info(tmp_repo: Path) -> None:
    paths = engine_paths(tmp_repo)
    (paths.root / "triage_rules.yaml").write_text(
        "rules:\n"
        "  - name: noise.csp\n"
        "    vuln_class: csp-script-src-wildcard\n"
        "    severity: info\n"
        "    reason: playbook-noise\n",
        encoding="utf-8",
    )
    # Re-use seed_nuclei_run_with_signal but inject a different payload —
    # copy its body into a local helper or extend it to take a payload arg.
    # The signal must have: template_id='csp-script-src-wildcard', severity='info'.
    _seed_nuclei_run_with_suppressible_signal(paths)

    engine.run_program(paths, "hackerone", "example", now="2026-05-12T05:00:00Z")

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    try:
        finding_hash, state, notes_path = conn.execute(
            "SELECT finding_hash, current_state, notes_path FROM findings"
        ).fetchone()
        hist = conn.execute(
            "SELECT to_state, actor, note FROM findings_state_history "
            "WHERE finding_hash = ?", (finding_hash,),
        ).fetchall()
    finally:
        conn.close()

    assert state == "resolved_info"
    assert notes_path == f"findings/_resolved/info/{finding_hash}.md"
    assert not (paths.root / "findings" / "_queue" / f"{finding_hash}.md").exists()
    assert (paths.root / "findings" / "_resolved" / "info" / f"{finding_hash}.md").exists()
    assert len(hist) == 1
    to_state, actor, note = hist[0]
    assert to_state == "resolved_info"
    assert actor == "triage-engine"
    assert note.startswith("rule=noise.csp template=csp-script-src-wildcard ")
    assert "reason=playbook-noise" in note
```

Define `_seed_nuclei_run_with_suppressible_signal(paths)` at module level
in `tests/triage/test_engine.py` (do **not** modify the existing
`seed_nuclei_run_with_signal` in `conftest.py`). The new helper is a
verbatim copy of `seed_nuclei_run_with_signal` with exactly two changes
inside its `signals.insert_signals([Signal(...)])` call: set the signal's
`signature` to `"csp-script-src-wildcard|primary|"` and its `payload` to
`'{"template_id":"csp-script-src-wildcard","severity":"info","name":"CSP wildcard"}'`.
Everything else (services row, recon_runs row, run_id) stays identical so
the existing seeding contract is reused without divergence.

- [ ] **Step 2: Run, expect FAIL**.

- [ ] **Step 3: Create `src/earn_money/triage/suppress.py`** containing
  `apply(conn, paths, finding, rule, *, version, now) -> None`. It must:

  1. Compute `notes_path = f"findings/_resolved/info/{finding.finding_hash}.md"`.
  2. Build a new `Finding` from the passed-in one with that `notes_path` and
     `current_state="queued"` (the DAO requires `queued` for new rows).
  3. Call `findings.upsert_finding(conn, new_finding)`.
  4. Render the notes body with `queue.render(new_finding, service=svc)`
     where `svc` is `services.pick_canonical_service(...)` — same call the
     engine already uses. Write it to `paths.root / notes_path`.
  5. Call `history.transition_state(conn, finding_hash=finding.finding_hash,
     to_state="resolved_info", actor="triage-engine",
     note=f"rule={rule.name} template={finding.vuln_class} version={version} "
     f"reason={rule.reason}", now=now)`.

- [ ] **Step 4: Modify `engine.py::_process_signal`** — after `classify(sig)`
  and before `findings.upsert_finding`, load rules once per `run_program`
  call (pass them down as a parameter; do not call `load_rules` per signal).
  Then:

  - If `existing is None` and `rules.match(rs, vuln_class=vuln_class,
    severity=severity_hint)` returns a rule, call `suppress.apply(...)`
    with `version = str(json.loads(sig.payload).get("info", {}).get("version", "unknown"))`
    and return `"created"`.
  - Otherwise: the existing branch is unchanged.

  Rules are loaded at the top of `run_program` via
  `rs = rules.load_rules(paths.root / "triage_rules.yaml")` (or `rs = []`
  if the file is absent — keep the helper tolerant for fresh checkouts).

- [ ] **Step 5: Run, expect PASS** (new test + all existing engine tests).

- [ ] **Step 6: `make smoke`** — must be green.

- [ ] **Step 7: Commit** as `feat(triage): engine routes rule-matched findings to _resolved/info/ with audit`.
