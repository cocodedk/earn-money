---
dos_authorized: false
destructive_payloads_authorized: false
social_engineering_authorized: false
auth_testing_authorized: true
mutation_testing_authorized: true
pii_handling: synthetic_data_only
max_requests_per_second: 10
authorized_test_environments:
  - target.cocode.dk
authorized_test_accounts: []
auth_lockout_budget: 10
sqli_time_based: false
injection_testing_authorized: true
extra_nuclei_dirs: []
special_notes: |
  Operator-owned OWASP Juice Shop at target.cocode.dk.
  Full HTTP technique authorization on the designated test environment.
  No real user PII — all data is synthetic (Juice Shop seed data).
  No DoS, no destructive payloads (no database wipes or file deletes).
---

# RoE — local/juice-shop

Operator-owned target. Overrides the repo-wide floor for this program only.
