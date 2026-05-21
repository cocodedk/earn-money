---
platform: local
slug: webgoat
policy: rate-limited-OK
in_scope:
  - webgoat.cocode.dk
out_of_scope: []
scope_hash: ""
last_synced: "2026-05-21T00:00:00Z"
---

# WebGoat fixture

Operator-owned OWASP WebGoat instance at `webgoat.cocode.dk`.
Server-rendered (Thymeleaf) — usable for stubs that don't need
SMTP / OAuth fixtures.

Has self-registration at `/WebGoat/registration`, login at
`/WebGoat/login`. No password-reset / SMTP flow.
