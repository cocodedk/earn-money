# 2026-05-13 follow-ups (A, B, C) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to implement task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close three gaps surfaced by the engagement-1 cycle 1 run on
`hackerone/security`. Three independent items, executable in order.

**Architecture:** Each item lives under
`docs/superpowers/plans/2026-05-13-followups/` as its own short file.
A and B are code work; C is configuration + research. CodeRabbit
review after every commit.

**Tech Stack:** Python 3.12+, sqlite3, `pyyaml`. Tests: `pytest`.
Lint/types: `ruff`, `mypy --strict`. Files ≤ 200 lines.

## Plans

1. [`A-apply-rules.md`](A-apply-rules.md) — Retroactive suppression CLI.
2. [`B-source-failure.md`](B-source-failure.md) — Investigate + fix nuclei batch failure.
3. [`C-onboard-program.md`](C-onboard-program.md) — Onboard a fresh low-density H1 program.

## Execution order

A → B → C. A and B are independent; A first because it cleans the
existing backlog and exercises one more piece of the pipeline. B
needs `recon/outputs/` artifacts from today's run on the VPS. C
involves cursor-driven research and an operator decision point.

## Out of scope

- The IPv6 egress decision (separate session — needs operator policy
  call, not code).
- The VPS scope-sync cron fix (needs cron config on the VPS, not in
  the repo).
- The httpx e2e binary path (low priority — doesn't block work).
