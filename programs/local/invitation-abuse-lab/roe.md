---
max_requests_per_second: 30
dos_authorized: false
destructive_payloads_authorized: false
social_engineering_authorized: false
pii_handling: synthetic_data_only
authorized_test_environments:
  - invitation-abuse-lab
authorized_test_accounts:
  - inviter
  - recipient
  - unrelated
special_notes: |
  allow_registration_probes enables invitation-abuse detection.
  Fixture-only mutating invite probes are allowed only for this local fixture
  with scanner-owned synthetic accounts and controlled email domains.
allow_active_login_probes: false
allow_password_reset_probes: false
allow_mfa_probes: false
allow_oauth_probes: false
allow_registration_probes: true
---

# RoE — local/invitation-abuse-lab

Invitation-abuse passive + controlled-acceptance fixture checks enabled.
