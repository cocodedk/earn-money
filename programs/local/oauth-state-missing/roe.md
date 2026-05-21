---
max_requests_per_second: 30
dos_authorized: false
destructive_payloads_authorized: false
social_engineering_authorized: false
pii_handling: synthetic_data_only
authorized_test_environments:
  - oauth-state-missing
authorized_test_accounts: []
special_notes: |
  Passive GET-only fixture. No credentials needed.
  allow_oauth_probes enables stub 2.15 detection chain.
allow_active_login_probes: false
allow_password_reset_probes: false
allow_mfa_probes: false
allow_oauth_probes: true
allow_registration_probes: false
---

# RoE — local/oauth-state-missing

OAuth passive discovery probe enabled. No mutation or account actions.
