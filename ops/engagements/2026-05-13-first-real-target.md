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

## Engagement outcome — 2026-05-13 cycle 1

- Nuclei completed: 15 services scanned, 25 min wall-clock, **0 new
  signals**, 1 source failure (one batch errored). Run status
  `partial`. Triage processed three runs (today's nuclei + 2 older
  httpx runs that had triaged_at=NULL), produced 0 new findings.
- Queue snapshot before this session already had 3 items from
  yesterday's nuclei run (created before triage_rules.yaml shipped):
  `missing-cookie-samesite-strict`, `csp-script-src-wildcard`,
  `weak-csp-detect` — all on `app.pullrequest.com`. The first two
  match suppression rules but only apply prospectively, so they
  remain queued. Operator decision pending.
- Existing `verified`-state finding (`cookies-without-httponly`) is
  the DEMO walk-through from yesterday, audit-noted "not for filing".
- [signal] Real outcome: **zero new candidates this cycle**. Cycle
  1 of 3 against `hackerone/security` per the pivot trigger in
  `01-target.md`. Hardened target + tight default template set +
  high researcher density meant we got nothing fresh today.
- [tooling] Source failure on one batch worth investigating before
  cycle 2 — could be a transient (rate-limit on the target) or a
  systematic batch bug. Check `recon/outputs/.../nuclei/.../stderr.txt`
  before re-running.
- [tooling] Suppression rules are prospective only — they don't
  retroactively clear existing queue items. Acceptable design choice,
  but the operator now has a queue full of "noise that would have
  been suppressed if run today." Should add a small CLI to
  apply-rules-retroactively against the existing queue, or just have
  operator clear them by hand once.

## What I'd do next session, in order

Aimed at shortening the path to the first paid bounty. The $5
milestone is a 60–120-day milestone per the design spec; these steps
shorten the *first-submission* time, which is the gating event.

1. **Fix scope-sync cron on the VPS.** The 25h-stale `last_synced`
   means recon is silently running on possibly-shifted scope between
   manual syncs. Should be a 30-minute fix.
2. **Decide IPv6 egress policy.** Either add `-4` to the recon tool
   commands (force IPv4 so the playbook'd IP is what triage sees) or
   register the IPv6 address in `ops/playbook.md` so audits aren't
   surprised. IPv6 leakage matters because triage cross-references
   IPs across programs.
3. **Onboard one low-density program** alongside `hackerone/security`.
   The latter is a real target but ~100% dupe rate on common findings.
   Picking a fresh small-B2B-SaaS or government BBP with low
   researcher density gets us closer to a non-dup finding.
4. **Run the engagement against the new program.** Same loop, same
   `bin/queue` / `bin/show` / Caido / `bin/draft` / `bin/submit`.
5. **Submit. Wait.** First submission for a new H1 handle takes
   2–6 months to pay even when valid; that timeline is the gate, not
   our pipeline.
