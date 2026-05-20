# Engagement 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship gaps G1–G3 from
[`../../specs/2026-05-13-engagement-1/03-gaps.md`](../../specs/2026-05-13-engagement-1/03-gaps.md)
so the operator can run a real triage session against `hackerone/security`:
`bin/queue` listing, `bin/show` detail, and in-engine suppression of
playbook-noise nuclei templates with an audit trail.

**Architecture:** A new `triage/rules.py` module loads a top-level
`triage_rules.yaml` data file and exposes a pure matcher. The triage
engine consults the matcher for every new signal; matches route to
`_resolved/info/` with a structured `findings_state_history.note`. Two
new operator CLIs (`bin/queue`, `bin/show`) read the existing DB and
queue markdown — no schema changes.

**Tech Stack:** Python 3.12+, sqlite3, `pyyaml`, `argparse`. Tests:
`pytest`. Lint/types: `ruff`, `mypy --strict`. Conventional Commits.

## Files

1. [`00-overview.md`](00-overview.md) — file structure, conventions, run-everything checklist.
2. [`01-rules-loader.md`](01-rules-loader.md) — Task 1: YAML rule loader.
3. [`02-rules-match.md`](02-rules-match.md) — Task 2: matcher + decision type.
4. [`03-engine-suppression.md`](03-engine-suppression.md) — Task 3: engine routes suppressed findings to `_resolved/info/`.
5. [`04-queue-cli.md`](04-queue-cli.md) — Task 4: `bin/queue` top-5 default + `--all`.
6. [`05-show-cli.md`](05-show-cli.md) — Task 5: `bin/show <hash>` with audit history.
7. [`06-playbook-update.md`](06-playbook-update.md) — Task 6: doc the new CLIs and preflight checklist.

Sequence is strict for Tasks 1→3 (rules.py is consumed by the engine).
Tasks 4 and 5 are independent of Task 3 and may be parallelised. Task 6
runs last.
