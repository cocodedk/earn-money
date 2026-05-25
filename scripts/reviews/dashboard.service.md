# Review: scripts/dashboard.service

## Findings

- High: The service points at the archived v1 dashboard path, not the active Dockerized app. `ExecStart=/opt/earn-money/bin/dashboard` at `scripts/dashboard.service:18` depends on a root-level `bin/dashboard`, but the active repo no longer has root `bin/`. Installing this unit on a fresh current checkout will produce a service that cannot start.

- Medium: The unit documents "no auth" and relies on host/Caddy/obscurity as the boundary at `scripts/dashboard.service:8`. If Caddy exposes `h1.cocode.dk` publicly, the dashboard is readable by anyone who reaches the hostname. Put authentication in the Caddy config or stop installing this unit for production-facing hosts.

## Checks

- No systemd verifier was run.
