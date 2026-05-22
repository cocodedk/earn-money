---
max_requests_per_second: 30
dos_authorized: false
destructive_payloads_authorized: false
social_engineering_authorized: false
pii_handling: synthetic_data_only
authorized_test_environments:
  - tenant-org-join-abuse-lab
authorized_test_accounts:
  - outside
  - owner
special_notes: |
  allow_registration_probes enables tenant-join detection.
  allow_tenant_join_attempt grants permission to POST /api/workspaces/:slug/join.
  Fixture-only mutating join probes are allowed only for this local fixture
  with scanner-owned synthetic accounts.
allow_active_login_probes: false
allow_password_reset_probes: false
allow_mfa_probes: false
allow_oauth_probes: false
allow_registration_probes: true
---

# RoE — local/tenant-org-join-abuse-lab

Tenant/org-join-abuse passive + controlled-join fixture checks enabled.
