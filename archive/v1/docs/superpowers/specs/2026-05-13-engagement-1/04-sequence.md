# 04 — Sequence

Five phases, in order. Each phase has one verify check.

## S1. Local: ship gaps G1–G3

Behind tests: `bin/queue` (G1), `bin/show` (G2), the noise rules + audit-row
writer (G3), and a playbook update with the new CLIs + preflight checklist.

**Verify:** `make test` green; both CLIs exercised on the smoke-loop
fixtures from `scripts/_phase4_smoke_lib.py`.

## S2. VPS: preflight

SSH to the VPS, pull, run the preflight checklist in
[`02-guardrails.md`](02-guardrails.md).

**Verify:** every checkbox passes. If any fails, halt and resolve before
proceeding.

## S3. VPS: passive recon cycle

Trigger a fresh passive cycle against `hackerone/security`:

```bash
bin/passive-recon hackerone/security
```

**Verify:** asset count delta against the prior run is in the DB; no
errors in the run log; no destructive scope diff fired the freeze flag.

## S4. VPS: active recon (first cycle)

Run httpx then nuclei against the resolved assets:

```bash
bin/httpx-probe hackerone/security
bin/nuclei-scan hackerone/security
bin/triage hackerone/security
```

**Verify:** triage engine produced at least one `_queue/` entry **or** every
emitted signal was auto-suppressed by G3 with a logged audit row. Empty
queue + zero suppressions = the runners didn't actually run; investigate.

## S5. Operator triage session

On VPS shell or after syncing DB + `_queue/` to laptop: `bin/queue` for the
top 5, `bin/show <hash>` per candidate, reproduce in Caido, promote the
first reproducible candidate to `_verified/` with a one-sentence impact
note, resolve the rest (`resolved_dupe` / `resolved_na` / leave queued).

**Verify:** success criterion in [`00-goal.md`](00-goal.md) met, or the
pivot trigger in [`01-target.md`](01-target.md) is armed for next session.

## Gap log

Maintain `ops/engagements/2026-05-13-first-real-target.md` during the
session: one-line bullet per gap hit, categorised loosely as `signal`,
`tooling`, `policy`, or `report`. No taxonomy ceremony — just a running
list, committed at session end.
