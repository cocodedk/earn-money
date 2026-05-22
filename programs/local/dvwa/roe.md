---
max_requests_per_second: 30
dos_authorized: false
destructive_payloads_authorized: false
social_engineering_authorized: false
pii_handling: synthetic_data_only
authorized_test_environments:
  - dvwa.cocode.dk
authorized_test_accounts:
  - admin
special_notes: |
  DVWA default canary account is `admin` / `password`. No registration
  endpoint — the admin account is the only available identity. Stubs
  that need a non-admin canary refuse with AUTH_FIXTURE_REQUIRED.
allow_active_login_probes: true
allow_password_reset_probes: false
allow_mfa_probes: false
allow_oauth_probes: false
allow_registration_probes: false
---

# RoE — local/dvwa

Active-login probes only — DVWA has no reset / MFA / OAuth /
registration flows by default. Stubs 2.1 (username-enumeration),
2.3 (missing-lockout), 2.4 (weak-rate-limiting) all run against
the `admin` account; 2.2 (weak-password-policy) doesn't because
the password-change form isn't on the public surface.
