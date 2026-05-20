# Slice 03 — Stub 2.5 canary (predictable reset token)

> Depends on slices 01 + 02. First real use of the mailbox helper.
> Same TDD pattern as stub 2.1.

## What stub 2.5 does

1. RoE gate: `allow_password_reset_probes=True`.
2. `authorized_test_accounts` non-empty.
3. `load_mailbox_backend()` is not None (or, for fixtures
   declared `none`-mode, refuse with `mailbox_required_for_reset`).
4. Resolve the reset endpoint via `_shared/auth/forms.discover_forms`
   (looking for a form with `flow_hint=password_reset`) OR via
   bounded GET probes against `candidate_reset_paths()`.
5. For one canary account, request a password reset.
6. `mailbox.wait_for_message(account_address, since=<probe-ts>,
   timeout_s=60)` — block for the email.
7. `extract_reset_token(msg)` → the token string.
8. Repeat steps 5-7 N times (default N=8) to collect a sample.
9. Run entropy / sequencing analysis on the tokens:
   * If tokens are sequential integers → CRITICAL.
   * If tokens have low Shannon entropy → HIGH.
   * If tokens reuse a prefix / contain a timestamp → MEDIUM.
   * Otherwise → INFO (no finding).

## Persistence

`Finding(category="auth_predictable_reset_token", severity=HIGH|CRITICAL,
status=CANDIDATE, data={...})`. Token values themselves are
redacted; only the analysis result is stored.

## Tests

* All RoE / fixture / mailbox-required gates fire correctly.
* `wait_for_message` timeout → `Finding(status=stale)`.
* 8 sequential integer tokens → CRITICAL finding.
* 8 high-entropy hex tokens → no finding.
* CAPTCHA / lockout abort signal between requests → halt + no
  finding.

## Live smoke

Against `https://juiceshop.cocode.dk/#/forgot-password` (Juice Shop's
reset endpoint). Operator's mailbox catches the 8 reset emails. The
runner emits a Finding only if Juice Shop's tokens are predictable
(spoiler: they're UUIDs, so the test PASSES with no finding —
which is also a valid demo of the negative path).

## Commit

`feat(stubs): 2.5 predictable-reset-token runner + canary smoke`
