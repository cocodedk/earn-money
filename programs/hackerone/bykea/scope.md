---
in_scope: []
last_synced: ''
out_of_scope: []
platform: hackerone
policy: rate-limited-OK
scope_hash: ''
slug: bykea
---

# bykea

Low-density H1 program onboarded 2026-05-15 as target #2 per
`docs/superpowers/plans/2026-05-15-operator-followups.md`.
Pakistani ride-hailing platform (Karachi-based, *.bykea.net).

Density signals from agent-coordinator's research:
- `resolve_d=73`, efficiency 100%, 8 G-indexed disclosures.
- Coordinator verdict: STRONG.
- **Program page explicitly allows scanning at 60 requests / 60 seconds.**
  That's well below the 10 req/s floor in `roe.md`, so the RoE rate cap
  binds tighter than the program's permission — fine.

Asset-class fit: web + API. Operator's strength.
Scope populated by `bin/scope-sync` on first run.
