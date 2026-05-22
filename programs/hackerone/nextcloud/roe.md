---
max_requests_per_second: 3
dos_authorized: false
destructive_payloads_authorized: false
social_engineering_authorized: false
pii_handling: one_redacted_screenshot
authorized_test_environments: []
authorized_test_accounts: []
allow_active_login_probes: false
allow_password_reset_probes: false
allow_mfa_probes: false
allow_oauth_probes: false
allow_registration_probes: false
special_notes: |
  Conservative floor. 3 req/s. Open-source project — no staging env needed
  for passive recon. Active auth probes require test accounts from Nextcloud.
---

# RoE — hackerone/nextcloud

Per-program Rules of Engagement. Conservative defaults apply.
Passive well-known-path probing and header analysis only at this stage.
