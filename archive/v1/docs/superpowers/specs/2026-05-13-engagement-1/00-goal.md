# 00 — Goal and success

## Why this engagement exists

To exercise the full pipeline against real data for the first time. The Phase 4
state-machine proof was a synthetic `demo/proof` program. The local
`hackerone/security` DB has 14 assets and zero findings. Tooling works in
isolation; the end-to-end loop has never been driven by a real signal.

The goal of this engagement is **pipeline integrity on real data**, not a paid
bounty. Median time-to-first-paid for a new HackerOne handle is 2–6 months
regardless of pipeline quality.

## Success criterion (single, hard)

> At least one finding survives auto-suppression, gets a manual reproduction
> attempt by the operator, and reaches one of: `verified` (awaiting filing),
> `resolved_dupe`, or `resolved_na` — with a one-sentence impact narrative
> attached in the audit-history `note` field.

A queue entry that is auto-suppressed, never reproduced, or has no impact
narrative does **not** satisfy this criterion. This is the tightening cursor
asked for in critique #1.

## What this engagement does *not* try to prove

- A first paid bounty.
- That `hackerone/security` is a good earnings target (it isn't — see
  [`01-target.md`](01-target.md)).
- That every operator-experience gap is closed (only the blocking ones).
- That the report templates are production-grade (drafting once on a real
  finding tells us whether they are).

## Anti-goals — explicit non-work

- No second program onboarded this session.
- No unparking of Phase 3c (katana, ffuf) or 3d (digest, phone ping).
- No new active-recon templates beyond what `nuclei` ships with by default.
- No score/exploitability ranking model.
