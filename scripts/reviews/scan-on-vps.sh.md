# Review: scripts/scan-on-vps.sh

## Findings

- Medium: The script always removes `flags/RECON_ENABLED` on exit at `scripts/scan-on-vps.sh:54`, even if the flag existed before this script started. That can unintentionally disable a pre-existing operator consent gate or interfere with a concurrent scan. Record whether the flag existed first, and only remove it if this script created it.

- Low: The remote command assumes `flags/` exists at `scripts/scan-on-vps.sh:55`. The current repo has that directory, but a partial remote checkout or hand-created install path will fail with a shell error rather than a clear diagnostic. Add `mkdir -p flags` before writing the flag.

## Checks

- `sh -n scripts/scan-on-vps.sh` passed.
