---
dos_authorized: true
destructive_payloads_authorized: true
social_engineering_authorized: false
auth_testing_authorized: true
mutation_testing_authorized: true
pii_handling: synthetic_data_only
max_requests_per_second: 0
authorized_test_environments:
  - target.cocode.dk
authorized_test_accounts:
  - admin@juice-sh.op
auth_lockout_budget: 0
sqli_time_based: true
injection_testing_authorized: true
extra_nuclei_dirs: []
special_notes: |
  Operator-owned OWASP Juice Shop at target.cocode.dk.
  ALL HTTP techniques authorized on this designated test environment —
  the RoE deliberately does not restrict the engine. There are no real
  users, no production data, no third-party assets. The site exists
  specifically as a PoC playground for the scanner.

  Social engineering remains disabled because it does not apply to an
  unattended target (no humans to engineer).
---

# RoE — local/juice-shop

Operator-owned PoC target. The scanner RoE for runtime gating lives at
[`scanner-roe.yaml`](scanner-roe.yaml) — that file flips every
`allow_*` flag in the `RoePolicy._GATED` table to True against this
host, and lifts every budget cap to effectively-unbounded.

This file (`roe.md`) documents the operator's standing authorization
for technique-level review; the runtime enforcement happens via the
companion YAML.
