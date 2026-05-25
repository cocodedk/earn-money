# Review: scripts/install-tools-vps.sh

## Findings

- Medium: The remote command embeds `VPS_PATH` inside single quotes without escaping it at `scripts/install-tools-vps.sh:15`. The default path is safe, but an override containing a single quote will break remote parsing and can change the command that is executed. Reuse the single-quote escaping helper pattern from `scan-on-vps.sh`, or pass the path as an argument to a remote shell wrapper.

## Checks

- `sh -n scripts/install-tools-vps.sh` passed.
