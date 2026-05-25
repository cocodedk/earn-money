# Review: scripts/run-mission.sh

## Findings

- Medium: Host lookup only searches the first page of targets. The request uses `page_size=200` at `scripts/run-mission.sh:55`, which is the configured maximum, but it never follows the API `next` link. If the target is older than the first 200 rows, host mode reports "No target" even though the target exists. Ambiguity detection is also limited to that first page. Prefer UUID-only operation for reliability, or follow pagination until `next` is empty.

- Medium: Ambiguous host handling exits through Python inside command substitution at `scripts/run-mission.sh:69` through `scripts/run-mission.sh:73`. Under `set -e`, that exits the shell immediately without the script's `die` wrapper or a consistent `[mission]` error. The stderr list is useful, but the control flow is abrupt. Have the Python helper emit a structured sentinel or capture the nonzero status and call `die`.

- Low: `TIMEOUT` is not validated before numeric comparison at `scripts/run-mission.sh:31` and `scripts/run-mission.sh:123`. A non-numeric value from the environment turns the timeout check into a shell test error and may leave the script polling without the intended deadline. Validate `TIMEOUT` as a positive integer before starting the mission.

- Low: Final result fetch failures are warnings only. If `/turns/` or `/notes/` cannot be fetched at `scripts/run-mission.sh:170` or `scripts/run-mission.sh:184`, the script still exits successfully after printing a warning. That is fine if summaries are optional, but if this script is used in automation, a completed mission with missing final evidence can look like a clean run.

## Checks

- `sh -n scripts/run-mission.sh` passed.
- `shellcheck scripts/run-mission.sh` passed with no findings.
