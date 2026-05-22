---
platform: local
slug: reset-canary
policy: rate-limited-OK
in_scope:
  - reset-canary
out_of_scope: []
scope_hash: ""
last_synced: "2026-05-21T00:00:00Z"
---

# reset-canary fixture

Operator-owned purpose-built vulnerable target — a tiny Node/Express
app under `fixtures/reset-canary/` that emits intentionally
predictable password-reset tokens. Designed for the Phase-2 reset-
flow stub family (2.5 predictable-reset-tokens, future 2.6/2.7/2.8/
2.9 extensions).

The container runs inside the same docker network as the scanner
(`scanner-net`) and reaches the operator-owned Mailpit sidecar for
SMTP. The backend reads captured mail via Mailpit's HTTP API
(MailpitBackend lands in a follow-up commit).

Authorised for any HTTP technique — same operator-controlled basis
as the other local fixtures.
