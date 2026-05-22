---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these
# six lines intact. Values below the comments are yours to change.
phase: 3
spec: 5
slug: session-fixation
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
---

# 3.5 Session fixation

> Phase 3 — Session management · Category: Session lifecycle

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

Detect login flows that fail to issue a new authenticated session identifier after authentication, or that accept a session identifier chosen before login. The runner cares because session fixation can let an attacker pre-establish a session value and later reuse it after the victim authenticates.

## Inputs

The runner receives a shared `ScanTarget` and writes shared `Evidence` records. This stub does not redefine either type.

Required inputs:

* `target`: shared `ScanTarget`.
* `base_url`: normalized target origin from `ScanTarget`.
* `http_client`: shared HTTP client with isolated cookie-jar support.
* `scanner_config`: stub-specific knobs listed below.

Required for confirmed testing:

* `test_account`: scoped username/email and password from fixture config, scan config, or approved credential store.
* `login_flow`: discovered login form/API metadata, or a fixture adapter that knows how to authenticate safely.

Optional inputs:

* `known_session_cookie_names`: cookie names from Phase 3 cookie checks.
* `logout_flow`: safe logout URL or API, used only for cleanup when available.
* `csrf_extractor`: shared helper for login forms with CSRF tokens.

Config knobs:

| Name | Default | Purpose |
| ---- | ------: | ------- |
| `enabled` | `true` | Allows this stub to run. |
| `max_login_attempts` | `1` | Prevents account lockout and noisy auth logs. |
| `request_timeout_ms` | `10000` | Per-request timeout. |
| `follow_redirects` | `false` | Keep login redirects visible as evidence. |
| `allow_login_submission` | `false` | Must be explicitly enabled with scoped credentials. |
| `allow_cookie_seed_test` | `false` | Only enable in fixtures or programs explicitly allowing cookie injection. |
| `cleanup_logout` | `true` | Attempt safe logout cleanup when a logout flow is known. |
| `redact_cookie_values` | `true` | Cookie values must be redacted before logs and findings. |

The runner must skip confirmed testing when scoped credentials are not available. It may still record a low-confidence candidate if passive evidence shows a suspicious login/session pattern, but it must not submit guesses.

## Detection logic

Detection is deterministic and compares session identifiers before and after a controlled login.

### 1. Discover or load the login flow

Use these sources, in order:

1. Explicit fixture adapter.
2. `login_flow` supplied by prior authentication discovery.
3. Previously discovered HTML login form with username/email and password fields.

Do not brute force login paths in this spec. Do not infer a login endpoint from hostname alone.

### 2. Anonymous baseline

Create a fresh isolated HTTP client and cookie jar.

1. `GET` the login page or app landing page.
2. Capture all `Set-Cookie` values.
3. Identify session-like cookies by name and context.
4. Store only redacted values or secure fingerprints.

Session-like cookie names include:

```text
PHPSESSID
JSESSIONID
ASP.NET_SessionId
connect.sid
sid
session
sessionid
auth
token
```

If no pre-login session cookie is set, the runner can still test whether login creates a session, but it cannot prove fixation through value reuse.

### 3. Controlled login comparison

Only run this step when `allow_login_submission=true` and a scoped `test_account` is available.

1. Refresh the login form if CSRF or hidden fields are present.
2. Submit exactly one valid login attempt.
3. Capture response status, redirects, `Set-Cookie` headers, and final authenticated landing page if redirects are followed by the shared login helper.
4. Compare pre-login and post-login session-like cookie fingerprints by cookie name, domain, and path.

Finding signals:

* Same session cookie name and same value fingerprint before and after successful login.
* Login response does not set any new session/auth cookie, and authenticated page uses the pre-login cookie.
* Session cookie value changes only in non-auth cookies while the auth-bearing cookie remains stable.

Rejection signals:

* The main session/auth cookie value changes after login.
* A new authenticated session cookie replaces the anonymous cookie.
* The pre-login cookie is expired or overwritten during login.

### 4. Optional cookie seed test

Only run when `allow_cookie_seed_test=true`, the target is a fixture or explicitly authorized, and the login flow is known safe.

1. Create a new isolated client.
2. Set a synthetic session-like cookie value before visiting the login page, using a cookie name observed from baseline evidence.
3. Perform the same single controlled login.
4. Check whether the synthetic value is preserved as the authenticated session value.

The synthetic cookie value must be obviously scanner-generated and must never resemble a real session token.

This optional test is not required for the first implementation. The no-rotation comparison is enough for the default runner.

### 5. Status and confidence

| Condition | Status | Confidence |
| --------- | ------ | ---------- |
| Pre-login session cookie value is reused after a successful controlled login. | `confirmed` | `high` |
| Optional cookie seed value becomes the authenticated session value. | `confirmed` | `high` |
| Login succeeds but no clear session/auth cookie can be identified. | `candidate` | `low` |
| Pre-login cookie is replaced or expired during login. | `rejected` | `high` |
| Test aborted because credentials are missing, CAPTCHA appears, rate limit triggers, or login safety is uncertain. | `stale` | `low` |

Do not create a confirmed finding without evidence of successful authentication using a scoped test account or fixture oracle.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Stub-specific types: `SessionFixationSignature`, `SessionFixationFinding`.

### `SessionFixationSignature`

```ts
export interface SessionFixationSignature {
  signature_id: string;
  login_url: string;
  login_method: "GET" | "POST";
  session_cookie_name: string;
  session_cookie_domain?: string;
  session_cookie_path?: string;
  comparison_mode: "pre_login_reuse" | "cookie_seed_acceptance";
  requires_valid_credentials: true;
  requires_cookie_seed_permission: boolean;
  confidence: "low" | "medium" | "high";
  enabled: boolean;
  created_at: string;
  updated_at: string;
}
```

### `SessionFixationFinding`

```ts
export interface SessionFixationFinding {
  finding_id: string;
  target_id: string;
  evidence_ids: string[];

  login_url: string;
  login_method: "GET" | "POST";
  authenticated: boolean;
  session_cookie_name: string;
  session_cookie_domain?: string;
  session_cookie_path?: string;

  pre_login_cookie_fingerprint?: string;
  post_login_cookie_fingerprint?: string;
  seeded_cookie_used: boolean;
  value_reused: boolean;

  comparison: {
    pre_login_observed: boolean;
    post_login_observed: boolean;
    cookie_replaced: boolean;
    cookie_expired: boolean;
    redirect_target_redacted?: string;
  };

  title: string;
  summary: string;
  remediation: {
    summary: string;
    steps: string[];
  };

  confidence: "low" | "medium" | "high";
  status: "candidate" | "confirmed" | "rejected" | "stale";
  safe: false;
  created_at: string;
  updated_at: string;
}
```

Evidence requirements:

* Pre-login cookie evidence with redacted values.
* Login request metadata with username redacted and password omitted.
* Login response cookie evidence with redacted values.
* Authenticated landing-page evidence or fixture oracle proving login success.
* Optional cleanup/logout evidence when cleanup is performed.

Recommended remediation:

* Generate a new session identifier immediately after successful authentication.
* Expire or overwrite anonymous pre-login session cookies during login.
* Reject or replace externally supplied session identifiers.
* Bind server-side session state to authentication state and regenerate identifiers when privilege changes.

## Safety

This check is active because it may submit a valid login and optionally seed a cookie in a controlled client.

Allowed:

* `GET` login page and safe authenticated pages.
* One valid `POST` or equivalent login request when `allow_login_submission=true`.
* One safe logout cleanup request when `logout_flow` is known and `cleanup_logout=true`.
* Optional cookie seed test only when `allow_cookie_seed_test=true`.

Not allowed:

* Password guessing.
* Username guessing.
* More than `max_login_attempts`.
* Testing real user accounts not explicitly scoped.
* Bypassing CAPTCHA, MFA, WAF, lockout, or rate limits.
* Continuing after `429`, lockout wording, abuse detection, or CAPTCHA.
* Cookie seed testing on normal targets unless explicitly authorized.
* Reusing captured session cookies outside the isolated test client.
* Accessing sensitive user data after login beyond the minimum proof of authenticated state.

PII and secrets:

* Never log passwords.
* Redact usernames/emails unless they are fixture-only synthetic identifiers.
* Never log raw cookie values.
* Store cookie fingerprints only with the project-approved secret hashing helper.
* Redact CSRF tokens, authorization headers, and session IDs.
* Do not send auth or cookie evidence to AI.

AI involvement: `None`.

There is no deterministic gap that requires AI. Login comparison, cookie fingerprinting, and classification are deterministic.

## Pass/fail check

A coding agent implementation passes when these assertions hold.

Positive assertions:

* It accepts a shared `ScanTarget` and writes shared `Evidence`.
* It does not redefine shared `ScanTarget` or `Evidence`.
* It uses an isolated cookie jar for the test.
* It captures pre-login session cookie fingerprints.
* It submits at most one valid login when explicitly enabled and scoped credentials exist.
* It refreshes CSRF or hidden fields before login when required.
* It proves login success using a fixture oracle, authenticated marker, or expected redirect.
* It compares pre-login and post-login session cookie fingerprints by name, domain, and path.
* It creates a `confirmed`, `high` finding when a pre-login session cookie survives successful login unchanged.
* It creates a `rejected`, `high` result or no vulnerability finding when the session cookie rotates.
* It marks the test `stale`, `low` when credentials, CAPTCHA, rate limits, or unsafe side effects block testing.
* It redacts credentials, CSRF tokens, and cookie values.
* It links each finding to at least one `Evidence` record.

Negative assertions:

* It must not submit guessed usernames or passwords.
* It must not perform more than the configured login attempt budget.
* It must not use real accounts unless explicitly scoped.
* It must not bypass MFA, CAPTCHA, WAF, rate limits, or lockout.
* It must not continue testing after `429`, lockout, or abuse detection.
* It must not run cookie seed testing unless explicitly enabled.
* It must not reuse captured cookies outside the isolated test client.
* It must not store raw passwords or cookie values.
* It must not send auth evidence to an LLM.
* It must not mark a finding confirmed without proof of successful authentication.

## Test fixtures

Use a new synthetic fixture slug: `session-lifecycle`.

Required fixture routes:

| Route | Behavior | Expected result |
| ----- | -------- | --------------- |
| `/fixation/login-vulnerable` | Sets anonymous `sid`, accepts valid login, keeps same `sid` authenticated. | `confirmed`, `high` |
| `/fixation/login-rotates` | Sets anonymous `sid`, accepts valid login, replaces `sid` after authentication. | `rejected`, `high` or no finding |
| `/fixation/login-no-pre-cookie` | No anonymous cookie, creates new authenticated session at login. | no fixation finding |
| `/fixation/login-csrf` | Login form uses per-request CSRF token and vulnerable/no-rotation behavior. | Runner refreshes token and detects correctly. |
| `/fixation/login-captcha` | Shows CAPTCHA or abuse marker before submit. | `stale`, `low`; runner stops. |
| `/fixation/cookie-seed-vulnerable` | In fixture mode, preserves scanner-seeded `sid` after login. | `confirmed`, `high` when seed test enabled. |
| `/fixation/cookie-seed-safe` | In fixture mode, replaces scanner-seeded `sid` during login. | `rejected`, `high` when seed test enabled. |

Seeded fixture account:

* Username: `alice@example.invalid`
* Password: fixture-provided secret
* Account state must reset between tests.

Compatibility fixtures:

* `dvwa` may be used for exploratory adapter work if the local fixture supports deterministic login and resettable state.
* `juice-shop` and `webgoat` may be used only as secondary compatibility checks, not primary acceptance fixtures.

## Acceptance criteria

The implementation is acceptable when:

* The check is deterministic against the fixture.
* It uses isolated clients and cookie jars.
* It performs no login unless `allow_login_submission=true`.
* It performs no cookie seed test unless `allow_cookie_seed_test=true`.
* It completes within the configured request and login budgets.
* It handles missing login forms, missing credentials, invalid CSRF, redirects, TLS failures, timeouts, and connection errors gracefully.
* It stops on CAPTCHA, MFA challenge, lockout, WAF block, abuse detection, or `429`.
* It redacts credentials, CSRF tokens, authorization headers, and cookie values.
* It stores findings with at least one evidence ID.
* It reports `confirmed`, `rejected`, and `stale` statuses correctly.
* It defines only `SessionFixationSignature` and `SessionFixationFinding` as stub-specific types.
* Unit tests cover login-flow extraction, CSRF refresh, cookie fingerprinting, rotation comparison, cookie expiration detection, seed-test gating, redaction, safety aborts, and negative assertions.
* Fixture tests cover vulnerable no-rotation login, safe rotation login, no pre-login cookie, CSRF login, CAPTCHA abort, cookie-seed vulnerable behavior, and cookie-seed safe behavior.
* AI is not called.
