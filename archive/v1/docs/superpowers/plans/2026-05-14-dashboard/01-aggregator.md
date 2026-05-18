# Task 1 — Aggregator

**Files:**
- Create `src/earn_money/dashboard/aggregator.py`
- Create `src/earn_money/registry.py` — `iter_registered_programs(paths)`
- Modify `src/earn_money/triage/findings.py` — add `count_findings_by_state(conn, *, platform, slug) -> dict[FindingState, int]` (zero-filled).
- Promote `_SEVERITY_RANK` + `_sort_key` from `triage/queue_cli.py` to `triage/severity.py`.
- Test: `tests/dashboard/test_aggregator.py`

Public function: `build_status(paths, *, now=None) -> dict[str, Any]`.
Pure read. Per-program errors don't kill the whole response.

## Reuse — call the existing API, don't re-parse

- `scope.read_scope(paths.scope_file(p, s))` — typed `Scope` (no raw `frontmatter.load`).
- `flags.is_program_frozen(paths, p, s)` + `flags.freeze_reason(paths, p, s)`.
- `findings.findings_in_state(conn, ..., state="queued")` + new `count_findings_by_state` + the promoted severity helper.
- DB open as **read-only URI** so a missing DB raises cleanly without auto-creating: `sqlite3.connect(f"file:{path}?mode=ro", uri=True)`. Programs whose `db.sqlite` doesn't exist yet are returned with zero counts, no file created.

## TDD

- [ ] **1. Failing test — empty (no programs)** asserts `programs == []`, `total_findings == 0`.

- [ ] **2. Failing test — one program with seeded findings**:
  ```python
  paths = engine_paths(tmp_repo)
  conn = db.open_db(paths.program_db("hackerone", "example"))
  try:
      seed_queued(conn)  # creates the finding
  finally:
      conn.close()
  status = aggregator.build_status(paths, now="2026-05-14T09:00:00Z")
  assert status["programs"][0]["finding_states"]["queued"] == 1
  assert all(k in status["programs"][0]["finding_states"]
             for k in get_args(FindingState))   # zero-filled
  ```

- [ ] **3. Failing test — FROZEN via the flags helper**:
  `flags.freeze_program(paths, "hackerone", "example", reason="test"); ...` → assert `frozen=True`, `frozen_reason` non-empty.

- [ ] **4. Failing test — `first_verified_with_operator_note=True`** when any program has a history row with `to_state in {verified, resolved_dupe, resolved_na, resolved_paid}`, `actor='operator'`, `note` non-empty.

- [ ] **5. Failing test — broken program is contained**: create a second program with `scope.md` but no DB; assert it still appears in the JSON with zero counts and the first program isn't broken.

- [ ] **6. Implement** — see file list above. The aggregator is a thin assembler over the new and existing helpers.

- [ ] **7. `make smoke`** green.

- [ ] **8. Commit + /simplify pass.**
