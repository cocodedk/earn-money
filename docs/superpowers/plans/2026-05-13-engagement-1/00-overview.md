# 00 — Overview

## File structure (created or modified)

**Created:**
- `src/earn_money/triage/rules.py` — YAML loader + matcher (pure). ≤ 100 lines.
- `src/earn_money/triage/suppress.py` — routes a matched finding to
  `_resolved/info/` + writes the audit row. Extracted from engine to
  keep engine.py under the 200-line cap. ≤ 80 lines.
- `src/earn_money/triage/queue_cli.py` — `bin/queue` implementation. ≤ 120 lines.
- `src/earn_money/triage/show_cli.py` — `bin/show` implementation. ≤ 100 lines.
- `triage_rules.yaml` (repo root) — initial four suppression rules.
- `bin/queue` — `sh` wrapper (mirrors `bin/triage` pattern).
- `bin/show` — `sh` wrapper.
- `tests/triage/test_rules.py` — loader + matcher tests.
- `tests/triage/test_queue_cli.py` — listing tests.
- `tests/triage/test_show_cli.py` — show tests.

**Modified:**
- `src/earn_money/triage/engine.py` — wire suppression decision into the
  new-finding branch. Goal: stay ≤ 200 lines (currently 179).
- `tests/triage/test_engine.py` — one new test asserting suppression
  routes to `_resolved/info/` with the correct audit note format.
- `ops/playbook.md` — document `bin/queue`, `bin/show`, and the
  pre-active-recon preflight checklist.

## Conventions to follow

- File size: every source file ≤ 200 lines. Engine is close to the cap;
  if a change would cross 200, extract a helper into `rules.py`.
- TDD: failing test → run → fail → implement → run → pass → commit.
- Imports: `from __future__ import annotations` at the top.
- Strict typing: full annotations, `mypy --strict` must pass.
- ISO timestamps via `earn_money._time.now_iso()` or `to_iso()`. Never
  embed `datetime.now()` directly in test seeds (see commit `d68eb07`).
- Conventional Commits enforced by hook. One commit per task.

## Verify-everything checklist (after each task)

```bash
make smoke
```

Runs `ruff check`, `mypy --strict`, `pytest`. Must be green before the
next task. If the pre-commit hook rejects, fix; **never** `--no-verify`.
