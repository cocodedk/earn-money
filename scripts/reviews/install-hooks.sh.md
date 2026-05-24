# Review: scripts/install-hooks.sh

## Findings

- No actionable findings. The script is small, scoped, and fails early if it is not run inside a git worktree or if expected hook files are missing.

## Checks

- `sh -n scripts/install-hooks.sh` passed.
