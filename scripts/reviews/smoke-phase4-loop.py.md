# Review: scripts/smoke-phase4-loop.py

## Findings

- High: The script cannot run against the active repo layout. It inserts `REPO / "src"` into `sys.path` at `scripts/smoke-phase4-loop.py:19`, but the active repo has no root `src/`; the `earn_money` package is under `archive/v1/src`. It also depends on helper behavior that copies root `templates/` and invokes root `bin/` CLIs. This smoke is currently a stale v1 smoke, not a current project smoke.

- Medium: The smoke does not fail when important subprocesses fail. `draft`, `submit`, and `ack-freeze` return codes are printed at `scripts/smoke-phase4-loop.py:54`, `scripts/smoke-phase4-loop.py:60`, `scripts/smoke-phase4-loop.py:78`, `scripts/smoke-phase4-loop.py:84`, and `scripts/smoke-phase4-loop.py:98`, but no assertion or nonzero exit is produced. A broken CLI can still yield an overall process exit of 0.

## Checks

- Python AST parse passed.
