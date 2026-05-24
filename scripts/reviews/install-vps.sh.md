# Review: scripts/install-vps.sh

## Findings

- High: The installer is still oriented around the archived v1 Python package instead of the active Dockerized Django stack. The post-install instructions call `pip install -e ".[dev]"` at `scripts/install-vps.sh:71` and `python -m earn_money.runners.passive_recon` at `scripts/install-vps.sh:78`, but the active repo root has no root `pyproject.toml` or root `src/earn_money`. A fresh operator following this script will not end up with the current app installed.

- High: The installer enables the stale dashboard/timer units through `install_dashboard_unit` and `install_passive_tick_timer` at `scripts/install-vps.sh:46` and `scripts/install-vps.sh:48`. Those units call root-level v1 paths such as `/opt/earn-money/bin/dashboard` and `/opt/earn-money/bin/passive-recon`, which are absent from the current repo.

## Checks

- `sh -n scripts/install-vps.sh` passed.
