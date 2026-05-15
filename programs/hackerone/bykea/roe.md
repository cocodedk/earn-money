---
dos_authorized: false
destructive_payloads_authorized: false
social_engineering_authorized: false
pii_handling: one_redacted_screenshot
max_requests_per_second: 1
authorized_test_environments: []
authorized_test_accounts: []
special_notes: |
  Bykea's H1 program — onboarded 2026-05-15. Program page explicitly
  allows scanning at 60 requests per 60 seconds (= 1 req/s sustained),
  reflected in max_requests_per_second above. The repo-wide floor
  otherwise applies: no DoS, no destructive payloads, no social
  engineering, PII limited to one redacted screenshot.

  If Bykea later names a sandbox or test account, capture that here.
---

# RoE — hackerone/bykea

Per-program Rules of Engagement. Overrides `CLAUDE.md`'s repo-wide
floor *for this program only*. Fields left unspecified inherit the
floor at read time.
