---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 2
spec: 7
slug: weak-expiry
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 2.7 Weak expiry

> Phase 2 — Authentication · Category: Password reset

<!--
GPT-5.5: Enrichment zone — paste-ready spec contract for LLM-assisted implementation.

Goal: enrich this spec so a coding agent can implement it safely and consistently.

PROTECTED — do not modify:
- YAML frontmatter (between `---` fences at top of file).
- Title heading, blockquote breadcrumb, and the `##` section headings.

EDITABLE — fill these:
- The body under each `##` section. Sub-headings (`###`), lists, code blocks, tables welcome.

OUTPUT FORMAT:
- Return raw markdown directly. Do NOT wrap the response in a ` ```markdown ` code fence.
- Inside the body, use exactly 3 backticks for code fences. No 4-backtick blocks.

CONTENT RULES:
- Use shared `ScanTarget` and `Evidence` from ../00-shared-schema.md. Do not redefine them.
- Define only stub-specific `<Name>Signature` and `<Name>Finding` types.
- Detection is deterministic. AI is `None` unless a deterministic gap is named under Safety.
- Pass/fail check has explicit assertions, including negative ones (what must NOT happen).
- Confidence: `low | medium | high`. Finding status: `candidate | confirmed | rejected | stale`.
- Never hard-code hostname → expected tech; detect from response evidence.
- Follow the Coding-agent rules in ../00-shared-schema.md.
-->

## Purpose

Detect password reset links or tokens that remain usable after the configured expiry window. A runner cares because long-lived reset tokens give attackers more time to use leaked emails, copied links, browser history, logs, or intercepted reset URLs.

## Inputs

The runner receives a shared `ScanTarget` plus password-reset test configuration.

Required inputs:

* `target`: shared `ScanTarget`
* `reset_request_url`: absolute or target-relative URL for starting a password reset
* `reset_submit_url`: optional absolute or target-relative URL for submitting a new password, if it cannot be derived from the reset link
* `canary_account`: an owned test account
* `canary_email_source`: fixture mailbox, local mail sink, API mailbox adapter, or test harness callback that returns reset emails for the canary account
* `max_allowed_token_age_seconds`: policy threshold used by the scanner
* `probe_after_seconds`: delay before attempting to use the reset token
* `request_timeout_seconds`
* `max_redirects`
* `user_agent`
* `tls_policy`
* `evidence_redaction`: enabled by default

Optional inputs:

* `reset_request_method`: default `POST`
* `reset_request_fields`: form or JSON field names for the canary email
* `new_password_generator`: produces a scanner-owned password for the canary account only
* `login_check_url`: URL used to verify whether the reset succeeded
* `login_check_fields`: form or JSON field names for login verification
* `csrf_config`: selector, cookie, or fixture-provided token source when the reset form requires CSRF
* `expected_success_markers`: response text, status, or redirect markers for a successful reset in a fixture
* `expected_failure_markers`: response text, status, or redirect markers for expired or invalid token handling
* `max_body_bytes`: default `65536`
* `rate_limit_backoff_seconds`: default `0`; do not retry aggressively

The canary account must be created for scanning. Do not run this stub against real user accounts.

## Detection logic

Detection is deterministic and uses only scanner-owned accounts.

### Flow

1. Start a password reset for the canary account.
2. Read the reset email from the configured canary email source.
3. Extract the reset URL and token from the email.
4. Store redacted evidence for:

   * reset request response
   * received email metadata
   * reset link shape
   * token age at probe time
5. Wait until `probe_after_seconds` has passed.
6. Attempt to use the same reset link or token.
7. Classify the result from HTTP status, redirect chain, response headers, response body markers, and optional login verification.
8. Record whether the token was accepted after the allowed expiry window.

### Token extraction

The runner may extract reset links from:

* `href` attributes in HTML email
* plain text URLs
* fixture-provided message metadata
* redirect targets from the reset request flow, only in local fixtures

The runner must redact token values before persistence or logging.

Store only:

* token parameter name, if present
* token length
* token character class summary
* token hash
* reset URL path
* query parameter names
* age at probe time
* whether the same token was accepted or rejected

Do not store the raw reset URL if it contains the token.

### Acceptance signals

A reset token is considered accepted after expiry when at least one strong signal is present:

* reset form loads successfully after `probe_after_seconds`
* password change submission succeeds after `probe_after_seconds`
* reset endpoint returns a success redirect after `probe_after_seconds`
* login with the newly set canary password succeeds after using the delayed token

A token is considered rejected when one or more clear failure signals are present:

* response says the token is expired, invalid, already used, or stale
* reset form is not shown
* reset submission is rejected
* login with the attempted new canary password fails
* response status is `400`, `401`, `403`, or fixture-defined expired-token status
* redirect leads to a restart-reset page without changing the password

### Classification

Use these confidence rules:

* `high`: delayed token use changes the canary password, and login with the new password succeeds.
* `medium`: delayed token use reaches a success state, but login verification is unavailable.
* `low`: delayed token still loads a reset form after the policy window, but no password-change confirmation is available.

Set finding status as:

* `confirmed`: delayed token is accepted after `max_allowed_token_age_seconds`.
* `rejected`: token is rejected after the expiry window.
* `candidate`: evidence suggests weak expiry, but the runner lacks login verification or clear success markers.
* `stale`: the reset flow could not be replayed because setup changed, the mailbox message expired before use, or the canary state no longer matches the scan run.

### Non-findings

Do not report weak expiry when:

* the reset token is rejected after the policy window
* the runner cannot obtain a reset token
* the reset flow requires unsupported interaction
* the mailbox adapter fails
* the canary account is locked or disabled
* the application returns generic text but does not accept the delayed token
* the delayed token is accepted only before `max_allowed_token_age_seconds`

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Define only stub-specific types:

```python
from dataclasses import dataclass, field
from typing import Literal

Confidence = Literal["low", "medium", "high"]
FindingStatus = Literal["candidate", "confirmed", "rejected", "stale"]

@dataclass(frozen=True)
class WeakExpirySignature:
    reset_request_url: str
    reset_submit_url: str | None
    reset_request_method: Literal["GET", "POST"]
    reset_link_path: str | None
    token_parameter_names: list[str]
    token_hash: str | None
    token_length: int | None
    token_charset_summary: str | None
    requested_at_epoch_ms: int
    probed_at_epoch_ms: int
    token_age_seconds: int
    max_allowed_token_age_seconds: int
    probe_after_seconds: int
    delayed_form_loaded: bool
    delayed_reset_submit_accepted: bool
    delayed_login_succeeded: bool | None
    expired_or_invalid_marker_seen: bool
    success_marker_seen: bool
    status_code: int | None
    redirect_chain: list[str] = field(default_factory=list)

@dataclass(frozen=True)
class WeakExpiryFinding:
    target: "ScanTarget"
    status: FindingStatus
    confidence: Confidence
    signature: WeakExpirySignature
    evidence: list["Evidence"]
    summary: str
    impact: str
    remediation: str
    detected_at_epoch_ms: int
```

Evidence records should include:

* reset request response evidence
* reset email metadata evidence
* redacted reset link evidence
* delayed probe response evidence
* optional login verification evidence

Evidence must not contain:

* raw reset token
* full reset URL containing the token
* mailbox credentials
* canary password
* session cookies
* CSRF token values
* real user email addresses

Use content hashes and redacted snippets for audit.

## Safety

This stub is mutating but constrained to a scanner-owned canary account.

Allowed behavior:

* submit one password reset request for the canary account
* read reset email from the configured canary mailbox or fixture sink
* wait for the configured expiry probe window
* submit one delayed reset attempt using the canary token
* optionally verify login for the canary account
* restore the canary account password if the fixture supports it

Not allowed:

* testing real user accounts
* requesting resets for discovered emails
* enumerating accounts
* brute forcing reset tokens
* guessing token formats
* trying multiple token variants
* replaying tokens from logs, browser history, or previous scans
* using leaked password lists
* bypassing CSRF controls
* altering account data beyond the canary password
* sending reset emails outside the configured canary mailbox
* following reset links to unrelated hosts
* sending raw reset tokens to logs, AI, telemetry, or reports

HTTP-method discipline:

* Use `GET` only to load forms or follow reset links.
* Use `POST` only for the configured reset request and reset submission.
* Do not use `PUT`, `PATCH`, or `DELETE`.
* Do not retry state-changing requests unless the transport failed before the request was sent and the project has an idempotency guard.

Payload restrictions:

* Use only the configured canary email.
* Use generated scanner-owned passwords.
* Limit body size and redirect count.
* Keep request count low and predictable.

PII handling:

* Redact email local parts where possible.
* Store only token hashes and metadata.
* Do not persist raw email bodies unless the fixture requires it; store redacted excerpts instead.

AI involvement: `None`.

A future AI summary layer must treat scanned content as untrusted evidence and must not receive raw reset tokens. This follows the project’s wider LLM safety rule that external scan data is evidence, not instructions. 

## Pass/fail check

The implementation passes when all assertions hold.

Positive assertions:

* The runner can request a reset for a scanner-owned canary account.
* The runner can extract a reset link from the configured mailbox or fixture sink.
* The runner redacts the raw token before persistence.
* The runner waits at least `probe_after_seconds` before using the token.
* The runner records `token_age_seconds`.
* The runner compares `token_age_seconds` with `max_allowed_token_age_seconds`.
* The runner reports `confirmed` with `high` confidence when a delayed token changes the canary password and login with the new password succeeds.
* The runner reports `candidate` when the delayed reset form loads after the policy window but no final password-change verification is available.
* The runner reports `rejected` when the delayed token is expired or invalid.
* The runner attaches evidence for request, email/link extraction, delayed probe, and optional login verification.
* The runner handles TLS, timeout, redirect, and mailbox errors without crashing.

Negative assertions:

* The runner must not test real user accounts.
* The runner must not request resets for emails discovered during scanning.
* The runner must not brute force or mutate reset tokens.
* The runner must not try many password variants.
* The runner must not log or persist raw reset tokens.
* The runner must not persist canary passwords.
* The runner must not follow reset links to hosts outside the `ScanTarget` allowlist.
* The runner must not classify weak expiry from email text alone.
* The runner must not classify weak expiry when the delayed token is rejected.
* The runner must not classify weak expiry when token use occurs before `max_allowed_token_age_seconds`.
* The runner must not use AI to decide whether the token was accepted.
* The runner must not retry mutating reset submissions in a loop.
* The runner must not report a confirmed finding without response or login evidence that the delayed token worked.

## Test fixtures

Use a new fixture slug: `weak-expiry-reset`.

The fixture should expose a small password reset flow with two modes:

* vulnerable mode: reset tokens remain valid longer than the scanner policy window
* fixed mode: reset tokens expire before or at the scanner policy window

Recommended fixture behavior:

* local web app with one canary account
* local mail sink or in-memory mailbox endpoint
* reset request endpoint:

  * `POST /forgot-password`
  * accepts `email`
  * sends reset link to fixture mailbox
* mailbox endpoint:

  * `GET /_test/mailbox?email=...`
  * returns latest canary reset email only inside the fixture network
* reset form endpoint:

  * `GET /reset-password?token=...`
* reset submission endpoint:

  * `POST /reset-password`
  * accepts `token`, `password`, and optional CSRF field
* login endpoint:

  * `POST /login`
  * verifies canary password

Suggested test profile:

* `max_allowed_token_age_seconds = 5`
* `probe_after_seconds = 7`
* vulnerable token lifetime: `60` seconds
* fixed token lifetime: `5` seconds

Required fixture cases:

1. Vulnerable token accepted after policy expiry.
2. Fixed token rejected after policy expiry.
3. Token accepted before policy expiry does not produce a finding.
4. Reset email missing produces `stale` or no finding.
5. Unsupported or external reset link is rejected safely.
6. Login verification unavailable downgrades confidence to `medium` or `low`.
7. Raw token is absent from persisted evidence and logs.
8. Reusing an already-used token does not produce a false positive.
9. Expired marker in body produces `rejected`.
10. Generic error page does not produce a confirmed finding.

If an existing fixture already has a controllable reset-token lifetime, reuse it only when the test can set short expiry windows deterministically. Do not depend on wall-clock waits longer than the test budget.

## Acceptance criteria

Operational requirements:

* Idempotent for repeated scan runs against the same fixture.
* Uses only scanner-owned canary account data.
* Completes inside the configured test budget.
* Keeps wall-clock waits short in tests.
* Handles timeout, TLS, DNS, mailbox, and redirect errors gracefully.
* Produces deterministic findings from HTTP and login evidence.
* Does not depend on hostname-specific assumptions.
* Detects reset flow behavior from response evidence.
* Stores redacted evidence with stable hashes.
* Does not leak raw tokens, cookies, CSRF values, or passwords.
* Does not perform brute force, token guessing, or account enumeration.
* Does not use flaky retries.
* Gives clear skip or stale reasons when the reset flow cannot be tested safely.
* Supports both vulnerable and fixed fixture modes.
* Produces stable confidence and status values from the documented rules.

