# 03 — Operator-experience gaps

The minimum set to fix before the operator's first real triage session. Each
is small enough to land in this engagement.

## G1. `bin/queue` — list pending findings

Reads `findings/_queue/` cross-referenced with the per-program SQLite. For
each pending entry, prints:

- short hash (first 8 chars)
- vuln class
- target asset
- severity (from the scanner output that produced the finding)
- `first_seen`

Sorted highest-severity first, then oldest-`first_seen` first. Default
shows the top 5 ([`02-guardrails.md`](02-guardrails.md)); `--all` shows the
whole queue.

## G2. `bin/show <hash>` — show one finding

Reads the queue markdown body plus the audit history rows from the DB. Prints
both, no SQL by the operator. Accepts a short hash prefix (the same one
`bin/queue` displays). Errors clearly on ambiguous prefixes.

## G3. Auto-resolve_info rules in the triage engine

Encodes the playbook's noise list as in-engine suppression rules. Initial
ruleset (one rule per nuclei template ID):

- `cookies-without-httponly`
- `csp-script-src-wildcard`
- `missing-cookie-samesite-strict`
- `tls-version` (info-tier matches only)

Each rule fires before `_queue/` enqueue, writes the audit row described in
[`02-guardrails.md`](02-guardrails.md), and routes the finding to
`_resolved/info/`. Rules are data, not code — a small YAML file consumed by
the engine. Adding a rule does not require code changes.

## Out of scope this engagement

- No `bin/dismiss` bulk-resolve CLI. The DB transition snippet in
  [`ops/playbook.md`](../../../ops/playbook.md) is enough for now; if the
  operator hits it more than three times in this session, it goes on the
  follow-up list.
- No exploitability/confidence score in `bin/queue` sort. We don't have data
  to model it yet.
- No report-template audit. Drafting one real report tells us what's missing.
