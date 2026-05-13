# Engagement 1 — first real-target run

**Date:** 2026-05-13
**Owner:** Babak Bandpey (cocode.dk)
**Status:** Draft — pending cursor + operator sign-off
**Parent design:** [`../2026-05-12-earn-money-design.md`](../2026-05-12-earn-money-design.md)

Phase 5 starts here. This is the first time the pipeline runs against a real
HackerOne program with the intent to produce, triage, and reproduce real
signals. Earnings are not the goal of this engagement.

## Files

1. [`00-goal.md`](00-goal.md) — what success looks like, what it doesn't.
2. [`01-target.md`](01-target.md) — target choice and the pivot trigger.
3. [`02-guardrails.md`](02-guardrails.md) — queue cap, preflight, audit trail.
4. [`03-gaps.md`](03-gaps.md) — operator-experience gaps fixed before triage.
5. [`04-sequence.md`](04-sequence.md) — order of operations across the session.

## What changed vs. cursor's critique

Cursor's review (2026-05-13) called out four weaknesses in the original
proposal. Each is now spec'd:

| # | Cursor critique | Where addressed |
|---|---|---|
| 1 | Success metric too permissive | [`00-goal.md`](00-goal.md) |
| 2 | No pivot trigger | [`01-target.md`](01-target.md) |
| 3 | No noise budget | [`02-guardrails.md`](02-guardrails.md) |
| 4 | No suppression audit trail | [`02-guardrails.md`](02-guardrails.md) |
