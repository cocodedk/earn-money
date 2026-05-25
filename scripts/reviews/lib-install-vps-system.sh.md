# Review: scripts/lib/install-vps-system.sh

## Findings

- High: `install_dashboard_unit` installs `scripts/dashboard.service` at `scripts/lib/install-vps-system.sh:35`, but that service points to `/opt/earn-money/bin/dashboard`, which is not present in the active repo. This makes the main VPS installer deploy a dead service.

- Medium: `install_caddy` proxies `h1.cocode.dk` to `127.0.0.1:8080` at `scripts/lib/install-vps-system.sh:64`. The current Docker stack exposes nginx on host port 80, and the backend itself is internal to Docker. Unless a separate v1 dashboard is also running on 8080, this Caddyfile points to the wrong service.

- Medium: `print_installed_versions` can abort the whole installer under the parent script's `set -e`. Version probes such as `subfinder -version | grep ...` at `scripts/lib/install-vps-system.sh:91` through `scripts/lib/install-vps-system.sh:105` are not guarded consistently. A missing binary or changed version text can turn a noncritical reporting step into installer failure.

## Checks

- `sh -n scripts/lib/install-vps-system.sh` passed.
