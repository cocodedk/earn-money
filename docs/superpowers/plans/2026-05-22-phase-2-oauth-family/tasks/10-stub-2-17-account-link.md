# Task 10 — Stub 2.17: oauth-account-linking detection chain

Implement passive discovery, classification, and fixture-mode active
checks in `oauth_account_linking/`. The work is split across two
sub-files to keep each under the 200-line cap.

## Sub-tasks

- [10a-classify.md](10a-classify.md) — Steps 1–4: `AccountLinkingFlawKind` enum,
  `test_classify.py`, and `classify.py`
- [10b-runner.md](10b-runner.md) — Steps 5–7: `test_runner.py`, detection chain
  wired into `runner.py`, coverage check, commit, and the "After Task 10"
  close-out steps
