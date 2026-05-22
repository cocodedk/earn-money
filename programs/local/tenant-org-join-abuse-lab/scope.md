---
platform: local
slug: tenant-org-join-abuse-lab
policy: rate-limited-OK
in_scope:
  - tenant-org-join-abuse-lab
out_of_scope: []
scope_hash: ""
last_synced: "2026-05-22T00:00:00Z"
---

# tenant-org-join-abuse-lab fixture

Operator-owned invite-tenant-lab container (SCENARIO=tenant-org-join).
Exposes multi-tenant workspace join flows in vulnerable and secure modes.
Tenant slug: acme. Vulnerable endpoint: POST /api/workspaces/acme/join.
