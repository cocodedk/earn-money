---
max_requests_per_second: 30
dos_authorized: false
destructive_payloads_authorized: false
social_engineering_authorized: false
pii_handling: synthetic_data_only
authorized_test_environments:
  - oauth-account-linking-lab
authorized_test_accounts:
  - user_a
  - user_b
special_notes: |
  allow_oauth_probes enables account-linking detection.
  allow_active_login_probes enables two-session state-binding checks.
  Fixture-only mutating link probes are allowed only for this local fixture
  with scanner-owned synthetic accounts.
allow_active_login_probes: true
allow_password_reset_probes: false
allow_mfa_probes: false
allow_oauth_probes: true
allow_registration_probes: false
---

# RoE — local/oauth-account-linking-lab

OAuth account-linking passive + active fixture checks enabled.
