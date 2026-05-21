---
max_requests_per_second: 30
dos_authorized: false
destructive_payloads_authorized: false
social_engineering_authorized: false
pii_handling: synthetic_data_only
authorized_test_environments:
  - reset-canary
authorized_test_accounts:
  - scanner@example.invalid
special_notes: |
  Operator-owned purpose-built reset-flow vuln target. State is
  in-memory only; restart-each-scan is the explicit design.
  Mail destinations resolve to the Mailpit sidecar — synthetic
  identifiers only, no real inboxes touched.
allow_active_login_probes: true
allow_password_reset_probes: true
allow_mfa_probes: false
allow_oauth_probes: false
allow_registration_probes: false
---

# RoE — local/reset-canary

`allow_password_reset_probes=true` is the load-bearing knob for the
Phase-2 reset-flow stubs (2.5 predictable-reset-tokens, then the
2.6/2.7/2.8/2.9 family). The other Phase-2 active-probe knobs are
off because this fixture only implements the reset surface.

Rate limit set to 30 r/s — fixtures can absorb bursts the
repo-wide 10 r/s floor would clamp. CLAUDE.md authorises any HTTP
technique against operator-owned fixture environments.
