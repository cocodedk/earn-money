---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 2
spec: 13
slug: mfa-reset-abuse
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 2.13 MFA reset abuse

> Phase 2 — Authentication · Category: MFA

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

Detect whether MFA reset, disablement, or re-enrollment flows can be abused to weaken account protection without proving control of the existing second factor. A runner cares because password reset security can be undone if an attacker who controls a password, email inbox, or active session can remove MFA, replace an authenticator, or generate recovery options without a strong step-up check.

## Inputs

The runner receives a shared `ScanTarget` and uses only the target, credentials, and policy supplied by the caller.

Required input:

* `ScanTarget` from `../00-shared-schema.md`
* Base URL in scope
* One test account with permission to inspect MFA settings
* Runner HTTP client with cookie/session isolation
* Evidence store from the shared scanner runtime

Optional input:

* Second test account for negative checks
* Known MFA settings paths, if the caller has provided them
* Login credentials for a dedicated test account
* Existing authenticated session for a dedicated test account
* Configured step-up timeout, default `120` seconds
* Maximum candidate paths to probe, default `25`
* Maximum requests per target, default `80`
* Allowlist of safe account-management paths
* `dry_run` mode, default `true`

Do not use:

* Real customer accounts
* Staff/admin accounts unless the scan scope explicitly allows them
* Leaked credentials
* OTP brute force
* Recovery-code brute force
* User enumeration as part of this stub

Config shape:

```python
class MfaResetAbuseConfig(TypedDict, total=False):
    known_mfa_paths: list[str]
    known_account_paths: list[str]
    max_candidate_paths: int
    max_requests: int
    step_up_timeout_seconds: int
    dry_run: bool
    allow_mutating_test_account_changes: bool
    restore_mfa_after_test: bool
```

`allow_mutating_test_account_changes` must default to `False`. When it is `False`, the runner must stop before submitting any request that could disable, reset, replace, or re-enroll MFA.

## Detection logic

Detection is deterministic and based on observed HTTP responses, forms, API metadata, redirects, status codes, and explicit account-management controls.

### Candidate discovery

Build a small candidate set from evidence found during authenticated navigation. Prefer links and forms discovered from the target over guessed paths.

Sources:

* Authenticated account page links
* Settings page links
* Security page links
* HTML forms
* JavaScript route strings visible in already-fetched pages
* API responses already collected by the runner
* Caller-provided `known_mfa_paths` and `known_account_paths`

Candidate terms:

* `mfa`
* `2fa`
* `two-factor`
* `totp`
* `authenticator`
* `security-key`
* `webauthn`
* `passkey`
* `recovery`
* `backup-code`
* `reset`
* `disable`
* `remove`
* `re-enroll`
* `reenroll`

Do not crawl the whole site. Do not fuzz broad path lists. Do not assume a product or framework from hostname.

Suggested low-volume fallback paths, only when authenticated pages provide no candidates:

```text
/account/security
/settings/security
/security
/profile/security
/account/mfa
/account/2fa
/settings/mfa
/settings/2fa
```

### Evidence classification

For each candidate response, classify the page or API as one of:

* `mfa_settings_view`
* `mfa_disable_flow`
* `mfa_reset_flow`
* `mfa_reenroll_flow`
* `recovery_code_regeneration`
* `unknown_account_security_page`
* `not_relevant`

Classification is based on response evidence, not URL alone.

Signals for MFA reset or disablement:

* Forms or buttons with labels such as `Disable MFA`, `Reset authenticator`, `Remove authenticator`, `Generate new recovery codes`, `Set up new device`
* API routes containing reset or disable semantics
* JSON keys such as `mfaEnabled`, `twoFactorEnabled`, `totpSecret`, `recoveryCodes`, `webauthnCredentials`
* HTTP methods that indicate state change: `POST`, `PUT`, `PATCH`, `DELETE`
* CSRF tokens attached to MFA-management forms
* Step-up challenge UI, such as password confirmation, OTP prompt, WebAuthn assertion, or recovery-code prompt

### Abuse checks

The runner checks whether sensitive MFA-management actions appear to require recent, strong verification.

A flow is suspicious when the target exposes an MFA reset, disable, recovery-code regeneration, or re-enrollment action and one or more of these conditions is observed:

1. The action page is reachable with only a normal authenticated session.
2. The form or API has no visible step-up requirement.
3. The response allows action preparation without asking for password, current OTP, WebAuthn assertion, recovery code, or equivalent proof.
4. The server accepts a non-mutating preflight or validation request without requiring step-up.
5. The action endpoint returns a success-shaped response to a safe test request that should have failed authorization.
6. The action can be reached immediately after password reset without a second factor challenge, when the scanner has evidence from the same run.

Do not infer abuse from the existence of an MFA settings page alone.

### Safe request discipline

The default runner is read-only.

Allowed by default:

* `GET`
* `HEAD`
* `OPTIONS`
* Authenticated navigation to settings pages
* Parsing forms and API metadata
* Detecting presence or absence of step-up controls
* Submitting explicitly safe preflight requests only when the project has a standard safe-request marker

Not allowed by default:

* Submitting a disable/reset/re-enroll form
* Regenerating recovery codes
* Removing WebAuthn/passkey credentials
* Replacing TOTP secrets
* Changing email, password, phone number, or MFA factors
* Confirming any action by clicking a destructive button
* Testing real OTP values or recovery codes
* Trying many OTP or recovery-code variants

When `allow_mutating_test_account_changes=true`, the runner may perform one controlled state-change check on a dedicated test account only if all of these are true:

* The scan scope permits it.
* The account was created for scanner testing.
* The current MFA state can be restored.
* The runner has a cleanup path.
* The request count stays within budget.
* The evidence clearly records the before and after state.
* The test does not affect other accounts, tenants, or shared data.

If any condition is missing, report a `candidate` finding instead of mutating state.

### Confidence rules

Use `high` confidence only when the runner observes a sensitive MFA-management action accepted without a step-up check on a dedicated test account.

Use `medium` confidence when the runner observes an exposed reset, disable, re-enrollment, or recovery-code regeneration flow with no visible step-up control, but does not submit the final action.

Use `low` confidence when the runner finds weak signals only, such as suspicious route names or labels without enough evidence to confirm whether step-up is enforced server-side.

### Rejection rules

Return `rejected` when:

* The candidate path is unrelated to MFA.
* A step-up challenge is clearly required before any sensitive MFA-management action.
* The server rejects safe preflight or action-preparation requests with `401`, `403`, or a step-up redirect.
* The runner cannot authenticate and no authenticated evidence is available.
* The only signal is a URL or route name with no matching response content.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them.

Define only stub-specific types:

```python
from typing import Literal, TypedDict

MfaResetAbuseAction = Literal[
    "disable_mfa",
    "reset_mfa",
    "reenroll_mfa",
    "regenerate_recovery_codes",
    "remove_factor",
    "unknown_mfa_management_action",
]

MfaResetAbuseStepUp = Literal[
    "none_observed",
    "password_required",
    "otp_required",
    "webauthn_required",
    "recovery_code_required",
    "email_confirmation_required",
    "unknown",
]

MfaResetAbuseStatus = Literal[
    "candidate",
    "confirmed",
    "rejected",
    "stale",
]

MfaResetAbuseConfidence = Literal[
    "low",
    "medium",
    "high",
]

class MfaResetAbuseSignature(TypedDict):
    signature_id: str
    action: MfaResetAbuseAction
    method: str
    path: str
    status_code: int
    content_type: str | None
    step_up_observed: MfaResetAbuseStepUp
    csrf_present: bool
    destructive_submission_blocked: bool
    mutating_check_performed: bool
    matched_terms: list[str]
    evidence_ids: list[str]

class MfaResetAbuseFinding(TypedDict):
    finding_id: str
    target_id: str
    status: MfaResetAbuseStatus
    confidence: MfaResetAbuseConfidence
    title: str
    summary: str
    affected_url: str
    action: MfaResetAbuseAction
    step_up_observed: MfaResetAbuseStepUp
    evidence_ids: list[str]
    signature: MfaResetAbuseSignature
    remediation: str
    safe_to_retry: bool
```

Persistence rules:

* Store one finding per distinct sensitive MFA-management action.
* Attach every finding to the shared target ID.
* Store raw HTTP evidence through the shared `Evidence` mechanism.
* Store only redacted request and response excerpts in the finding.
* Never persist OTP values, recovery codes, passwords, cookies, bearer tokens, CSRF tokens, or full session headers in the finding body.
* Evidence IDs must be stable for the scan run.
* A previous `confirmed` finding may become `stale` when the endpoint no longer exists or now requires step-up.

Recommended evidence records:

* Authenticated security settings page
* MFA-management form or API metadata
* Step-up challenge response, when present
* Server rejection response for safe preflight checks
* Controlled success response, only when mutation is explicitly allowed and scoped to a test account

## Safety

This stub is read-only by default.

### HTTP-method discipline

Default allowed methods:

* `GET`
* `HEAD`
* `OPTIONS`

Conditional methods:

* `POST`
* `PUT`
* `PATCH`
* `DELETE`

Conditional methods may be used only when the scanner framework marks the request as safe, or when `allow_mutating_test_account_changes=true` and the account is a dedicated test account.

### Payload restrictions

Do not send:

* OTP guesses
* Recovery-code guesses
* Password guesses
* New authenticator secrets
* New WebAuthn registrations
* New phone numbers
* New email addresses
* Payloads copied from destructive forms unless dry-run handling is guaranteed
* Payloads that click or confirm destructive account changes

Safe preflight payloads may include scanner-owned invalid placeholders only when the expected result is rejection and the endpoint is known not to change state on invalid input.

### PII handling

The runner may process the test account username or email if needed for login. It must not include it in the finding summary unless the shared schema already allows account identifiers for test accounts.

Redact:

* Email addresses outside dedicated test accounts
* Phone numbers
* Recovery codes
* OTP values
* TOTP secrets
* WebAuthn credential IDs where they identify a user device
* Session cookies
* Authorization headers
* CSRF tokens
* Passwords

### AI involvement

AI: `None`.

No model is needed for this stub. Classification is based on deterministic response evidence, route metadata, form fields, and status codes.

A future deterministic gap may be named if the scanner needs to classify unusual account-security text across languages. Until that gap is explicitly added, do not use an LLM for this stub.

## Pass/fail check

The implementation passes when all assertions below are true.

### Positive assertions

* The runner accepts a shared `ScanTarget`.
* The runner uses shared `Evidence` for HTTP request and response records.
* The runner defines `MfaResetAbuseSignature` and `MfaResetAbuseFinding`.
* The runner can authenticate with a dedicated test account when credentials are provided.
* The runner discovers MFA-management candidates from authenticated response evidence.
* The runner classifies MFA disable, reset, re-enrollment, and recovery-code regeneration controls.
* The runner records whether a step-up challenge was observed.
* The runner emits a `candidate` finding with `medium` confidence when a sensitive MFA-management flow is reachable and no step-up control is visible.
* The runner emits a `confirmed` finding with `high` confidence only when a scoped mutating test proves the action succeeds without step-up.
* The runner emits `rejected` when the flow clearly requires password, OTP, WebAuthn, recovery-code, or equivalent step-up.
* The runner stores redacted evidence IDs in each finding.
* The runner completes within configured request and time budgets.
* The runner handles unauthenticated targets by returning no confirmed finding and recording a safe rejection reason.

### Negative assertions

* The runner must not disable MFA by default.
* The runner must not reset MFA by default.
* The runner must not regenerate recovery codes by default.
* The runner must not remove passkeys, WebAuthn credentials, authenticators, phone factors, or email factors by default.
* The runner must not submit OTP guesses.
* The runner must not submit recovery-code guesses.
* The runner must not brute force any MFA reset path.
* The runner must not use leaked credentials.
* The runner must not test against real user accounts.
* The runner must not hard-code hostname-to-technology assumptions.
* The runner must not report a confirmed finding from URL text alone.
* The runner must not treat CSRF presence as proof of MFA step-up.
* The runner must not log cookies, authorization headers, passwords, OTPs, recovery codes, or TOTP secrets.
* The runner must not call an LLM.
* The runner must not retry destructive requests after ambiguous network failures.
* The runner must not continue mutating checks if cleanup fails.

Example pass/fail test skeleton:

```python
def test_mfa_reset_abuse_does_not_mutate_by_default(runner, target, test_account):
    result = runner.run(target, credentials=test_account, config={"dry_run": True})

    assert result.completed is True
    assert all(e.method in {"GET", "HEAD", "OPTIONS"} for e in result.http_evidence)
    assert not any("disable" in e.redacted_body.lower() and e.method == "POST" for e in result.http_evidence)


def test_mfa_reset_abuse_candidate_when_no_step_up_visible(runner, target, test_account):
    result = runner.run(target, credentials=test_account)

    finding = result.finding_by_slug("mfa-reset-abuse")
    assert finding.status == "candidate"
    assert finding.confidence in {"low", "medium"}
    assert finding.signature["step_up_observed"] in {"none_observed", "unknown"}
    assert finding.signature["destructive_submission_blocked"] is True


def test_mfa_reset_abuse_rejected_when_step_up_required(runner, target, test_account):
    result = runner.run(target, credentials=test_account)

    finding = result.finding_by_slug("mfa-reset-abuse")
    assert finding.status == "rejected"
    assert finding.signature["step_up_observed"] in {
        "password_required",
        "otp_required",
        "webauthn_required",
        "recovery_code_required",
        "email_confirmation_required",
    }


def test_mfa_reset_abuse_never_logs_sensitive_values(runner, target, test_account, log_capture):
    runner.run(target, credentials=test_account)

    logs = log_capture.text
    assert test_account.password not in logs
    assert "Authorization:" not in logs
    assert "Cookie:" not in logs
    assert "recovery_code" not in logs.lower()
    assert "totp_secret" not in logs.lower()
```

## Test fixtures

Preferred fixture: `webgoat` if a controlled MFA-reset or 2FA-management lesson is available in the local test stack.

Fallback fixture: create a new local fixture named `mfa-reset-abuse`.

The fixture should expose two modes.

### Vulnerable mode

Feature:

* Dedicated test account can log in.
* MFA is enabled on the account.
* `/account/security` links to an MFA management page.
* The page exposes a reset, disable, or recovery-code regeneration action.
* The action is reachable with only the normal authenticated session.
* No password, OTP, WebAuthn, or recovery-code step-up is required before the action.
* In dry-run mode, the runner can detect the missing step-up without submitting the final action.
* In scoped mutating mode, the action succeeds for the dedicated test account and can be restored.

Expected result:

* `candidate`, `medium` confidence in default dry-run mode
* `confirmed`, `high` confidence only when scoped mutation is explicitly enabled

### Safe mode

Feature:

* Dedicated test account can log in.
* MFA is enabled on the account.
* `/account/security` links to an MFA management page.
* Reset, disable, and recovery-code regeneration actions require step-up.
* The server rejects access without recent password confirmation, OTP, WebAuthn assertion, or recovery code.

Expected result:

* `rejected`
* Evidence records the step-up requirement
* No destructive action is submitted

### Fixture routes

Suggested local routes:

```text
GET  /login
POST /login
GET  /account/security
GET  /account/security/mfa
POST /account/security/mfa/disable
POST /account/security/mfa/reset
POST /account/security/mfa/recovery-codes/regenerate
GET  /account/security/step-up
POST /account/security/step-up
```

The vulnerable fixture may return success for the action endpoints without step-up only when the test account is used.

The safe fixture must require step-up before any action endpoint succeeds.

## Acceptance criteria

* The runner is idempotent in default mode.
* Default mode performs no destructive account change.
* Mutating checks require explicit config and a dedicated test account.
* The runner restores MFA state after any scoped mutating test.
* The runner refuses mutating checks when cleanup cannot be verified.
* The runner finishes within the configured request budget.
* The runner does not retry ambiguous destructive requests.
* The runner handles TLS errors gracefully and records a safe failure reason.
* The runner handles redirects without leaving scan scope.
* The runner handles expired sessions by reauthenticating once, then failing safely.
* The runner handles CSRF-protected forms without treating CSRF as MFA step-up.
* The runner records enough evidence for audit without storing secrets.
* The runner produces deterministic output for the same fixture state.
* The runner uses `low`, `medium`, or `high` confidence only.
* The runner uses `candidate`, `confirmed`, `rejected`, or `stale` status only.
* The runner does not use AI.
* The runner follows the shared coding-agent rules in `../00-shared-schema.md`.

