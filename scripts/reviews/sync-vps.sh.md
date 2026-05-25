# Review: scripts/sync-vps.sh

## Findings

- High: `rsync --delete` can delete remote runtime state that the script header claims to protect. The staged tree comes from `git archive HEAD`, so gitignored runtime files are absent; the rsync excludes protect `.env`, overrides, and `flags/`, but not `recon/outputs/` or `programs/**/db.sqlite` at `scripts/sync-vps.sh:42` through `scripts/sync-vps.sh:47`. Those are documented as sensitive runtime state in `CONTRIBUTING.md`. Add excludes for those paths before using this for production syncs.

- Low: The remote restart command embeds `VPS_PATH` inside single quotes without escaping it at `scripts/sync-vps.sh:51`. The default path is safe, but a path override containing a single quote breaks remote parsing. Use a quoting helper or pass the path as an argument to `sh -c`.

## Checks

- `sh -n scripts/sync-vps.sh` passed.
