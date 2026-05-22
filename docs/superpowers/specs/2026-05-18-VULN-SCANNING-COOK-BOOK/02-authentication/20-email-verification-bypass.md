---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 2
spec: 20
slug: email-verification-bypass
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 2.20 Email verification bypass

> Phase 2 — Authentication · Category: Registration

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

Detect registration flows where an account can be used before the email address is verified. A runner cares because many systems depend on email verification for account ownership, abuse prevention, trial limits, invite control, or access to user-only features. This check proves whether an unverified account can authenticate or reach protected functionality without clicking a verification link.

## Inputs

The runner receives a shared `ScanTarget` and may receive optional registration data from scan config.

Required:

* `ScanTarget`
* Base URL in scope
* HTTP client with cookie jar support
* Safe test email alias or mailbox sink owned by the test environment
* Unique test username prefix for idempotent runs

Optional:

* Existing low-privilege credentials for comparison
* Registration path hints, such as `/register`, `/signup`, `/api/register`, or app-specific routes
* Login path hints, such as `/login`, `/signin`, or `/api/login`
* Protected path hints, such as `/account`, `/profile`, `/dashboard`, or `/api/me`
* Maximum request budget
* Whether account creation is allowed by the scan rules of engagement
* Cleanup hook, if the fixture supports account deletion

Config knobs:

* `allow_account_creation`: default `false` unless the target is a lab fixture or RoE allows it
* `max_registration_attempts`: default `1`
* `max_login_attempts`: default `1`
* `max_protected_paths`: default `5`
* `timeout_ms`
* `follow_redirects`: default `true`
* `store_response_snippets`: default `true`
* `redact_email_local_part`: default `true`

The runner must not create accounts on production targets unless the scan configuration explicitly allows mutating registration tests.

## Detection logic

The check is deterministic and uses only HTTP evidence.

### 1. Discover candidate registration and login endpoints

Use already-known crawl results first. If no crawl results exist, probe only common unauthenticated paths within the same origin and request budget.

Candidate registration signals include:

* HTML form with password field and email field
* Submit button or label containing `register`, `sign up`, `create account`, or equivalent route text
* API endpoint returning registration-related validation errors
* Links from login page to registration page

Candidate login signals include:

* HTML form with password field and username or email field
* API endpoint returning login-related validation errors
* Links named `login`, `signin`, or equivalent route text

Do not infer framework or product type from hostname. Use response evidence only.

### 2. Create one synthetic account when allowed

If `allow_account_creation=false`, stop with no finding and record skipped evidence.

If allowed, submit one account registration using a unique synthetic identity:

* Email address must be owned by the test environment or local fixture.
* Username must include a random suffix.
* Password must be randomly generated for this test run.
* Do not use real user accounts.
* Do not use leaked credentials.
* Do not retry many variants.

Record evidence for:

* Registration request metadata
* Registration response status
* Redirect chain
* Response body snippet
* Set-Cookie headers, with values redacted
* Any text indicating verification is required

Verification-required signals include:

* `verify your email`
* `email verification`
* `confirmation email`
* `activate your account`
* `check your inbox`
* `account is inactive`
* `email not verified`
* API fields such as `requiresVerification`, `emailVerified: false`, `verified: false`, or `status: pending`

### 3. Attempt login without verifying email

Immediately attempt one login with the newly created account.

Classify the login result:

* `login_blocked`: login fails or response states email verification is required
* `session_issued`: login returns authenticated session cookie, token, or redirect to authenticated area
* `ambiguous`: response does not clearly prove either state

Session evidence includes:

* New session cookie after login
* Bearer token or JWT-like access token in response
* Redirect to authenticated area
* `/me`, `/profile`, or equivalent endpoint returns the synthetic account identity

Cookie and token values must be redacted before persistence.

### 4. Attempt protected access without verifying email

If login appears successful, request up to `max_protected_paths` known protected paths.

Protected access is confirmed when at least one authenticated-only action or page is available before verification.

Examples of protected access evidence:

* Account profile page returns HTTP 200 with synthetic username or email
* `/api/me` returns user object and `emailVerified=false`
* Dashboard page loads with authenticated content
* User settings page loads
* API returns user-specific data for the synthetic account

Do not perform destructive actions. Do not submit profile changes, purchases, messages, invites, password changes, or email changes.

### 5. Finding classification

Create a confirmed finding only when both are true:

1. The application indicates the email is unverified, pending, inactive, or requires confirmation.
2. The unverified account can authenticate or access protected user-only functionality.

Create a candidate finding when:

* The runner observes a session after registration or login, but cannot prove email verification state.
* The runner observes verification-required text but protected access evidence is incomplete.
* The app exposes only partial authenticated state, such as a session cookie but no accessible `/me` or profile endpoint.

Reject when:

* Registration is unavailable.
* Account creation is not allowed by config.
* Login is blocked until verification.
* Protected pages redirect to verification-required or login pages.
* The app allows only a verification notice page and no user-only functionality.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them.

Define only stub-specific types:

```ts
export type EmailVerificationBypassSignature = {
  registration_endpoint: string;
  login_endpoint?: string;
  protected_endpoint?: string;
  verification_required_signal?: string;
  session_signal?: "cookie" | "token" | "redirect" | "authenticated_identity";
  unverified_state_signal?: string;
  access_granted_before_verification: boolean;
  method: "GET" | "POST";
  evidence_ids: string[];
};

export type EmailVerificationBypassFinding = {
  target: ScanTarget;
  signature: EmailVerificationBypassSignature;
  evidence: Evidence[];
  status: "candidate" | "confirmed" | "rejected" | "stale";
  confidence: "low" | "medium" | "high";
  summary: string;
  impact: string;
  remediation: string;
  created_account_ref?: string;
};
```

Evidence should include:

* Candidate registration page or endpoint
* Registration request summary, with generated credentials redacted
* Registration response
* Verification-required signal, when present
* Login response
* Session signal, with cookies and tokens redacted
* Protected endpoint response proving access
* Rejection reason when no bypass is found

Do not persist full passwords, full session cookies, full bearer tokens, email inbox content, or verification links.

## Safety

This check is mutating because it may create an account. It must only run when account creation is allowed by scan config and RoE.

HTTP discipline:

* Use `GET` for discovery.
* Use one `POST` for registration when allowed.
* Use one `POST` for login when needed.
* Use `GET` for protected access checks.
* Do not perform state-changing authenticated actions after login.

Payload restrictions:

* Use only synthetic test accounts.
* Use only mailbox addresses controlled by the test harness.
* Do not use real customer, employee, or guessed user emails.
* Do not brute force forms, tokens, usernames, or passwords.
* Do not request or click verification links.
* Do not bypass email verification through token guessing.
* Do not use leaked password lists.
* Do not test against real user accounts.
* Do not attempt account takeover.

PII handling:

* Redact email local part unless fixture assertions need exact matching.
* Redact passwords entirely.
* Redact cookies, JWTs, bearer tokens, CSRF tokens, and verification tokens.
* Store only short response snippets needed to prove behavior.

AI involvement: `None`.

Deterministic gap:

* If the app uses unusual copy or a custom API shape, the runner may miss the verification-required state. Do not use AI to infer it. Mark the result `candidate` or `rejected` with low confidence unless deterministic evidence proves the bypass.

## Pass/fail check

A passing implementation must satisfy these assertions.

Confirmed finding assertions:

* Given a fixture with email verification enabled and a vulnerable flow, the runner creates one synthetic account.
* The runner records evidence that verification is required or that the account is unverified.
* The runner logs in before using any verification link.
* The runner reaches at least one protected page or API as the unverified account.
* The finding status is `confirmed`.
* The confidence is `high` when both unverified state and protected access are proven.
* The finding includes at least one evidence ID for registration, login, and protected access.
* Stored evidence redacts passwords, cookies, tokens, and verification links.

Candidate finding assertions:

* If the runner gets a session but cannot prove the email verification state, status is `candidate`.
* If the runner proves verification-required text but cannot prove protected access, status is `candidate` or `rejected` based on available evidence.
* Candidate findings use `low` or `medium` confidence, not `high`.

Rejected assertions:

* If registration is not found, no confirmed finding is created.
* If `allow_account_creation=false`, no account is created and no confirmed finding is created.
* If login is blocked until verification, status is `rejected`.
* If protected pages redirect to login or verification notice, status is `rejected`.
* If only a verification notice page is accessible, status is `rejected`.

Negative assertions:

* The runner must not click verification links.
* The runner must not read or parse real mailbox content outside the fixture mailbox sink.
* The runner must not create more than one account unless config explicitly allows more.
* The runner must not test real user accounts.
* The runner must not guess verification tokens.
* The runner must not use leaked credentials.
* The runner must not perform authenticated state-changing actions after login.
* The runner must not store raw passwords, raw cookies, raw bearer tokens, raw JWTs, CSRF tokens, or verification tokens.
* The runner must not infer vulnerability from hostname or expected technology.
* The runner must not call AI.

## Test fixtures

Preferred fixture: new `email-verification-bypass` fixture.

The fixture should expose two modes:

* `safe`: registration succeeds, email verification is required, login before verification is blocked.
* `vulnerable`: registration succeeds, email verification is required, but login and `/api/me` work before verification.

Fixture behavior:

* `POST /register` creates a synthetic account with `email_verified=false`.
* Registration response says the user must verify email.
* `POST /login` in `safe` mode returns 403 or equivalent verification-required response.
* `POST /login` in `vulnerable` mode issues a session for the unverified account.
* `GET /api/me` in `vulnerable` mode returns the synthetic account and `email_verified=false`.
* `GET /api/me` in `safe` mode redirects or returns 401/403 until verification.

Optional existing fixtures:

* `juice-shop` may be used only if the project already has a stable, documented registration flow that can be reset between tests.
* `dvwa` is not a good primary fixture for this stub unless a custom registration module is added.
* `webgoat` is not a good primary fixture unless the relevant lesson exposes an unverified-registration flow in a deterministic container state.

The fixture must reset state between test runs or accept unique synthetic account names without flaking.

## Acceptance criteria

Operational requirements:

* The check is idempotent when run with unique account suffixes.
* The check completes within the configured request budget.
* The check uses deterministic response evidence only.
* The check handles missing registration pages without error.
* The check handles CSRF-protected forms when tokens are present in the registration page.
* The check handles redirects without losing cookie state.
* The check handles TLS errors according to shared scanner policy.
* The check times out cleanly and records partial evidence.
* The check does not retry account creation unless the failure is a transport error and retry is allowed by shared policy.
* The check produces `rejected`, not `confirmed`, when evidence is incomplete.
* The check stores enough evidence for audit without storing secrets.
* The check follows shared coding-agent rules from `../00-shared-schema.md`.

Quality bar:

* Unit tests cover endpoint discovery, registration gating, login blocking, protected access, redaction, and finding status.
* Integration tests cover both safe and vulnerable fixture modes.
* The implementation does not hard-code hostnames, fixture names, or expected technologies into detection logic.
* The implementation does not call AI.
* The implementation does not perform destructive or account takeover behavior.

