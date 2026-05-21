---
max_requests_per_second: 30
dos_authorized: false
destructive_payloads_authorized: false
social_engineering_authorized: false
pii_handling: synthetic_data_only
authorized_test_environments:
  - webgoat.cocode.dk
authorized_test_accounts:
  - h1@cocode.dk
special_notes: |
  Scanner-owned canary account is `h1@cocode.dk` (password in
  FIXTURE_TEST_PASSWORD env). WebGoat has self-registration; no
  SMTP / reset / MFA / OAuth flows on the public surface.
allow_active_login_probes: true
allow_password_reset_probes: false
allow_mfa_probes: false
allow_oauth_probes: false
allow_registration_probes: true
---

# RoE — local/webgoat

Login probes + registration probes enabled. Reset / MFA / OAuth
flows aren't on WebGoat's default surface.
