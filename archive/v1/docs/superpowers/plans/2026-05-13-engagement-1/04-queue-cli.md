# Task 4 — `bin/queue`

**Files:**
- Create: `src/earn_money/triage/queue_cli.py`
- Create: `bin/queue`
- Create: `tests/triage/test_queue_cli.py`

List pending findings: short hash, vuln_class, asset, severity, first_seen.
Default top 5 (severity DESC, then first_seen ASC). `--all` shows full queue.

Severity order (DESC): `critical > high > medium > low > info > unknown`.

- [ ] **Step 1: Failing test — empty queue**

```python
from __future__ import annotations
from pathlib import Path
import pytest
from earn_money.triage import queue_cli
from tests.triage.conftest import engine_paths


def _run(root: Path, argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    rc = queue_cli.main(["--root", str(root), *argv])
    return rc, capsys.readouterr().out


def test_queue_empty_prints_no_findings_message(
    tmp_repo: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    paths = engine_paths(tmp_repo)  # registers hackerone/example program
    rc, out = _run(paths.root, ["--program", "example"], capsys)
    assert rc == 0
    assert "no queued findings" in out.lower()
```

- [ ] **Step 2: Failing test — top-5 default + sort**

Use `tests.triage.conftest.make_finding` to seed seven `queued` findings,
overriding `finding_hash`, `severity_hint`, and `first_seen` for each.
Severities: one `critical`, two `high` (with `first_seen` 03:00 and 04:00
Z so the older sorts first), one `medium`, one `low`, two `info`. Insert
each via `findings.upsert_finding(conn, make_finding(...))`. Then:

```python
rc, out = _run(paths.root, ["--program", "example"], capsys)
assert rc == 0
rows = [line for line in out.splitlines() if not line.startswith(("hash", "-"))]
rows = [line for line in rows if line.strip()]  # drop header/blank
assert len(rows) == 5
# Severity column is the second field — verify the order.
sevs = [line.split()[1] for line in rows]
assert sevs == ["critical", "high", "high", "medium", "low"]
```

- [ ] **Step 3: Failing test — `--all` shows everything**

Same seven seeds; call `_run(..., ["--program", "example", "--all"], ...)`
and assert seven body rows in the same sort order
(`["critical", "high", "high", "medium", "low", "info", "info"]`).

- [ ] **Step 4: Run all three, expect FAIL** (module not defined).

- [ ] **Step 5: Implement `src/earn_money/triage/queue_cli.py`**

Use `argparse`. Args: `--platform` (default `hackerone`), `--program`
(required), `--root` (default `Path.cwd()`), `--all` (flag, default False).

The DB is the source of truth for finding state (per the parent design
spec). `_queue/<hash>.md` is the human-readable surface, written by the
engine atomically when the queued row is inserted. So queue listing
reads from the DB only, no `_queue/` directory scan.

Body:

1. Open DB via `db.open_db(paths.program_db(platform, slug))`.
2. `findings.findings_in_state(conn, platform=…, slug=…, state="queued")`.
3. Sort: `(_SEVERITY_RANK[f.severity_hint], f.first_seen)` where rank maps
   `critical=0, high=1, medium=2, low=3, info=4, unknown=5`. Lower rank
   = higher severity.
4. If not `--all`, slice to `[:5]`.
5. If empty, print "no queued findings for `hackerone/example`" and exit 0.
6. Print one row per finding: `f"{f.finding_hash[:8]}  {f.severity_hint:<8} "
   f"{f.vuln_class[:32]:<32}  {f.asset[:32]:<32}  {f.first_seen}"`.
   Header line above the rows.

- [ ] **Step 6: Create `bin/queue`**

```sh
#!/bin/sh
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ -f "$ROOT/.env" ]; then . "$ROOT/.env"; fi
if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "queue: .venv not found at $ROOT/.venv — run 'make install-dev' first" >&2
  exit 1
fi
exec "$ROOT/.venv/bin/python" -m earn_money.triage.queue_cli --root "$ROOT" "$@"
```

`chmod +x bin/queue`. Mirrors `bin/triage` exactly except for the module path.

- [ ] **Step 7: Run all tests, expect PASS**.

- [ ] **Step 8: `make smoke`**, then commit as `feat(bin): queue CLI — top-5 default, --all override`.
