---
platform: local
slug: oauth-state-missing
policy: rate-limited-OK
in_scope:
  - oauth-state-missing
out_of_scope: []
scope_hash: ""
last_synced: "2026-05-22T00:00:00Z"
---

# oauth-state-missing fixture

Operator-owned oauth-lab container (SCENARIO=state-missing).
Exposes a vulnerable login→auth redirect that omits `state`, and a
safe variant that includes `state`.
