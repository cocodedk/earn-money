# Review: scripts/passive-tick.sh

## Findings

- High: The script assumes root-level v1 CLIs exist at `$ROOT/bin/scope-sync` and `$ROOT/bin/passive-recon` at `scripts/passive-tick.sh:37` and `scripts/passive-tick.sh:53`. The active repo has no root `bin/`, so the daily tick cannot perform useful work on a current checkout.

- Medium: Missing `programs/` is treated as a successful empty run. Both `find "$ROOT/programs"` calls at `scripts/passive-tick.sh:28` and `scripts/passive-tick.sh:42` can fail, but the script does not use `set -e` and still reaches `log "done"` at `scripts/passive-tick.sh:57`. That hides a broken deployment as a clean tick.

## Checks

- `sh -n scripts/passive-tick.sh` passed.
