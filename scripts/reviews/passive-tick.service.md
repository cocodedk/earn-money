# Review: scripts/passive-tick.service

## Findings

- Medium: The service does not load `/opt/earn-money/.env` or any environment file. `scripts/passive-tick.service:11` starts `passive-tick.sh`, which then invokes scanner CLIs that historically needed provider/API credentials. The install instructions copy `.env`, but this systemd unit never imports it, so timer runs may silently operate without required credentials.

- Medium: The service delegates to `scripts/passive-tick.sh`, which currently calls root-level v1 `bin/` CLIs. On the active repo layout, this service can be enabled successfully but fail on every timer run.

## Checks

- No systemd verifier was run.
