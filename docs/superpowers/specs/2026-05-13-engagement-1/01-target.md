# 01 — Target and pivot

## Target: `hackerone/security`

Already loaded. Real scope (`*.vpn.hackerone.net`, `hackerone.com`,
`pullrequest.com`, S3 buckets, user-content domains, etc.), policy
`rate-limited-OK`, freshly synced.

Continuing here goes against the design spec's selection guidance
("low researcher density, asset class operator knows well") and the dup-rate
on this program is essentially 100% for common findings. That cost is
accepted for this engagement because the goal is pipeline integrity, not
earnings — see [`00-goal.md`](00-goal.md).

## Pivot trigger

This engagement is **timeboxed to three active-recon cycles** on
`hackerone/security`. After the third cycle, evaluate against the success
criterion:

> If no candidate has survived suppression + reproduction with an impact
> narrative, the next session opens with target re-selection.

"Three cycles" is concrete: three nightly active-recon runs (or three
on-demand `bin/nuclei-scan` invocations) plus the daily passive cycle.

The pivot is **not** triggered by zero queue entries — empty queue is a
normal day. It is triggered by the absence of a *real* finding after the
pipeline has had three swings.

## Pivot target selection (next session, not this one)

When the pivot fires, the next session does deliberate target selection
informed by what this engagement actually surfaced: which template families
fired, which asset classes produced signal, where the noise concentrated.
That data does not exist yet, so picking now is guessing.

## What stays out

- No second program added in parallel. The spec is one program at a time
  through Phase 5.
- No promotion of a `manual-only` or `ambiguous` program — the recon runners
  refuse to start against those regardless.
