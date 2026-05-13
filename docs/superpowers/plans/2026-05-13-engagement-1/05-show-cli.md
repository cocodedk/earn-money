# Task 5 — `bin/show`

**Files:**
- Create: `src/earn_money/triage/show_cli.py`
- Create: `bin/show`
- Create: `tests/triage/test_show_cli.py`

Show one finding: the body of its `notes_path` markdown file followed by
the audit history from `findings_state_history`. Accepts a short hash
prefix. Errors clearly on ambiguous or missing prefixes.

- [ ] **Step 1: Failing test — unique prefix prints body + history**

```python
from __future__ import annotations
from pathlib import Path
import pytest
from earn_money import db
from earn_money.triage import findings, history, show_cli
from tests.triage.conftest import engine_paths, make_finding


def _run(
    root: Path, argv: list[str], capsys: pytest.CaptureFixture[str],
) -> tuple[int, str, str]:
    rc = show_cli.main(["--root", str(root), *argv])
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


def test_show_prints_body_and_history(
    tmp_repo: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    paths = engine_paths(tmp_repo)
    finding_hash = "a" * 8 + "1" + "0" * 55
    f = make_finding(
        finding_hash=finding_hash,
        notes_path=f"findings/_queue/{finding_hash}.md",
    )
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        findings.upsert_finding(conn, f)
    finally:
        conn.close()
    body_path = paths.root / f.notes_path
    body_path.parent.mkdir(parents=True, exist_ok=True)
    body_path.write_text("BODY-OF-FINDING\n", encoding="utf-8")

    rc, out, _ = _run(
        paths.root, ["--program", "example", finding_hash[:8]], capsys,
    )
    assert rc == 0
    assert "BODY-OF-FINDING" in out
    assert "audit history" in out.lower()
```

- [ ] **Step 2: Failing test — ambiguous prefix returns error**

Seed two findings whose `finding_hash` values share the first 8 chars
(e.g. `"a"*8 + "1" + "0"*55` and `"a"*8 + "2" + "0"*55`). Call `_run(...,
["--program", "example", "a"*8], capsys)`. Assert `rc == 1` and the
captured stderr contains `"ambiguous"`.

- [ ] **Step 3: Failing test — missing prefix returns error**

`paths = engine_paths(tmp_repo)` (no findings seeded). Call `_run(...,
["--program", "example", "deadbeef"], capsys)`. Assert `rc == 1` and the
captured stderr contains `"no finding"`.

- [ ] **Step 4: Run, expect FAIL** (module not defined).

- [ ] **Step 5: Implement `src/earn_money/triage/show_cli.py`**

Args: `--platform`, `--program`, `--root`, positional `prefix`.

Body:

1. Open DB.
2. `rows = conn.execute("SELECT finding_hash, notes_path FROM findings "
   "WHERE platform=? AND slug=? AND finding_hash LIKE ?",
   (platform, slug, prefix + "%")).fetchall()`.
3. If `len(rows) == 0`: stderr "show: no finding matching prefix
   `<prefix>` in `<platform>/<slug>`"; return 1.
4. If `len(rows) > 1`: stderr "show: ambiguous prefix `<prefix>` —
   matches N findings: <comma-list of first 12 chars>"; return 1.
5. Else: read and print the body of `paths.root / notes_path`. Then print
   a header `--- audit history ---` and call
   `history.state_history_for_hash(conn, finding_hash)`, printing one row
   per `StateChange` as `f"{sc.changed_at}  {sc.from_state or '∅'} → "
   f"{sc.to_state}  · {sc.actor}  · {sc.note or ''}"`.
6. Return 0.

- [ ] **Step 6: Create `bin/show`** (same shell-wrapper pattern as `bin/queue`,
  module is `earn_money.triage.show_cli`). `chmod +x`.

- [ ] **Step 7: Run all tests, expect PASS**.

- [ ] **Step 8: `make smoke`**, then commit as `feat(bin): show CLI — body + audit history by hash prefix`.
