# Live dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` (or `subagent-driven-development`) to
> implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A live web dashboard the operator can leave open in a browser
to see pipeline state across all registered programs without asking
Claude — queue counts, recent recon runs, last-synced timestamps, and
a generic "first verified with operator note" predicate. Read-only.

**Architecture:** Python stdlib `ThreadingHTTPServer` (no new deps).
Runs on the VPS; operator opens via SSH tunnel
(`ssh -L 8080:localhost:8080 recon-vps`). Browser polls a single
`/api/status` JSON endpoint every **10 s**. The dashboard never writes
to any DB or finding state, and opens program DBs in read-only URI
mode so a missing `db.sqlite` is a clean "no data yet" instead of an
auto-created empty file.

**Tech stack:** Python 3.12+, `sqlite3`, `http.server`,
`json.dumps`, vanilla HTML/CSS/JS. Tests: `pytest`. ≤200 lines per
file (project default); each plan task file ≤ ~50 lines per operator
preference.

## Plan files

1. [`00-overview.md`](00-overview.md) — files, conventions, status schema.
2. [`01-aggregator.md`](01-aggregator.md) — Task 1: aggregator module.
3. [`02-server.md`](02-server.md) — Task 2: HTTP server + routes.
4. [`03-index-html.md`](03-index-html.md) — Task 3: single-page HTML.
5. [`04-bin-wrapper.md`](04-bin-wrapper.md) — Task 4: bin/dashboard.
6. [`05-integration.md`](05-integration.md) — Task 5: e2e test.

## Execution order

Strict: 1 → 2 → 3 → 4 → 5. Server depends on aggregator; HTML
depends on the JSON shape from aggregator; bin/dashboard depends on
server; integration test exercises all four.

## Anti-goals

No auth, no writes, no per-user state, no historical timeseries
storage, no chart libraries (server-side aggregation only).
