# Review: scripts/setup-repo.sh

## Findings

- No actionable findings.

## Residual Risk

- The script writes `.github/CODEOWNERS` at `scripts/setup-repo.sh:55` through `scripts/setup-repo.sh:57` but does not commit it. That is reasonable for a setup helper; the operator still needs to inspect and commit the resulting file.

## Checks

- `sh -n scripts/setup-repo.sh` passed.
