---
max_requests_per_second: 30
dos_authorized: false
destructive_payloads_authorized: false
social_engineering_authorized: false
pii_handling: synthetic_data_only
authorized_test_environments:
  - juiceshop.cocode.dk
authorized_test_accounts:
  - h1@cocode.dk
special_notes: |
  Operator-owned vuln-app fixture. Scanner-owned canary account
  `h1@cocode.dk` is pre-registered; password lives in
  FIXTURE_MAILBOX_IMAP_PASSWORD (re-used as canary login password).
allow_active_login_probes: true
allow_password_reset_probes: true
allow_mfa_probes: true
allow_oauth_probes: true
allow_registration_probes: true
---

# RoE — local/juice-shop

All five Phase 2 active-probe knobs enabled — this is a fixture
target the operator owns. CLAUDE.md authorises any HTTP technique
against `juiceshop.cocode.dk`.

Rate limit is operator-set at 30 req/s — fixtures can handle bursts
better than live H1 programs. The repo-wide floor (10 r/s) caps it
when settings.RATE_LIMIT_SHARED_FLOOR_RPS is the default.
