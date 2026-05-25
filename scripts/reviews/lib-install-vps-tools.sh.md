# Review: scripts/lib/install-vps-tools.sh

## Findings

- Medium: Tool installation is not reproducible. `install_pd_tools` always resolves GitHub `latest` at `scripts/lib/install-vps-tools.sh:15`, and `install_go_tools` uses `@latest` or `@master` at `scripts/lib/install-vps-tools.sh:78` through `scripts/lib/install-vps-tools.sh:84`. A clean VPS install can change behavior day to day, or start failing when upstream raises Go/runtime requirements. Pin versions in one place and update intentionally.

- Low: Helper functions change the process working directory (`cd /opt/recon-tools` at `scripts/lib/install-vps-tools.sh:9`, `cd /tmp` at `scripts/lib/install-vps-tools.sh:58`) and do not restore it. Current callers use absolute paths afterward, but this makes the helpers brittle if reused or reordered.

## Checks

- `sh -n scripts/lib/install-vps-tools.sh` passed.
