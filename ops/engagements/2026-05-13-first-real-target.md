# Engagement 1 — 2026-05-13 — `hackerone/security`

Running log of gaps and observations during the first real engagement
session. One bullet per gap, loosely tagged `signal`, `tooling`,
`policy`, or `report`. Append-only during the session.

## Preflight

- [tooling] `last_synced` in `programs/hackerone/security/scope.md` was
  25h old (2026-05-12T13:00 vs now 2026-05-13T14:49). Scope-sync cron
  on the VPS appears not to be running — or is running but not as
  frequently as the spec assumes. Fix this session by manual sync; the
  recurring cause is a separate follow-up.
- [tooling] VPS has a second egress address on IPv6
  (`2a01:4f8:1c18:908b::1`). IPv4 still matches the recorded
  `178.105.140.53`. Active recon tools may hit IPv6 endpoints and leak
  a different source address into HackerOne triage logs. Need either
  an IPv6 record in `ops/playbook.md` or a `-4` flag on the recon
  tools to force IPv4 egress.
- [tooling] `make smoke` on the VPS skipped 3 httpx e2e tests because
  the binary lives at `/usr/local/bin/httpx` (per the install-vps
  script) but the e2e fixture looks at `~/go/bin/httpx`. Not blocking
  but worth fixing — the e2e suite gives up coverage for no reason.

## Active recon — first cycle

- [tooling] **Found via this engagement:** `bin/httpx-probe` exec'd
  `earn_money.runners.httpx_probe` instead of `httpx_probe_cli`. The
  non-CLI module has no `main()` so the wrapper exited 0 with no work
  done, no DB row, no error. Silent no-op — would have masked a stalled
  pipeline indefinitely. Fixed in `bin/httpx-probe`. `bin/nuclei-scan`
  already points at the right `_cli` module, so this was a one-off.
