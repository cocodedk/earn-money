# Review: scripts/_phase4_smoke_lib.py

## Findings

- High: The helper targets the archived v1 layout, not the active repo layout. It imports `earn_money` modules at `scripts/_phase4_smoke_lib.py:16`, copies `repo / "templates"` at `scripts/_phase4_smoke_lib.py:65`, and invokes CLIs from `repo / "bin"` at `scripts/_phase4_smoke_lib.py:129` and `scripts/_phase4_smoke_lib.py:150`. The active repo root has no `src/`, `templates/`, or `bin/`; those are under `archive/v1/`. Any current-root smoke run that uses this helper fails before exercising the state machine.

- Medium: `run_bin` returns subprocess results without enforcing success at `scripts/_phase4_smoke_lib.py:126`. Callers can print failures and continue, which lets the smoke report a ledger even when `draft`, `submit`, or `ack-freeze` failed. Either raise on nonzero return codes here or make the orchestration script assert every expected zero/nonzero outcome explicitly.

## Checks

- Python AST parse passed.
