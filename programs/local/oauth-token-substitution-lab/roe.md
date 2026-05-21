---
max_requests_per_second: 30
dos_authorized: false
destructive_payloads_authorized: false
social_engineering_authorized: false
pii_handling: synthetic_data_only
authorized_test_environments:
  - oauth-token-substitution-lab
authorized_test_accounts:
  - user_a
  - user_b
special_notes: |
  Two scanner-owned synthetic accounts. Active code-substitution
  test requires allow_oauth_probes=true.
allow_active_login_probes: true
allow_password_reset_probes: false
allow_mfa_probes: false
allow_oauth_probes: true
allow_registration_probes: false
---

# RoE — local/oauth-token-substitution-lab

Active OAuth token substitution test enabled with two synthetic accounts.
