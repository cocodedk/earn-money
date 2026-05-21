---
max_requests_per_second: 30
dos_authorized: false
destructive_payloads_authorized: false
social_engineering_authorized: false
pii_handling: synthetic_data_only
authorized_test_environments:
  - oauth-redirect-uri-lab
authorized_test_accounts: []
special_notes: |
  GET-only probes. allow_oauth_probes enables redirect URI mutation testing.
allow_active_login_probes: false
allow_password_reset_probes: false
allow_mfa_probes: false
allow_oauth_probes: true
allow_registration_probes: false
---

# RoE — local/oauth-redirect-uri-lab

OAuth redirect URI mutation probes enabled (pre-auth, GET only).
