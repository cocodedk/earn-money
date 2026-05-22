---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these
# six lines intact. Values below the comments are yours to change.
phase: 3
spec: 6
slug: no-rotation-after-login
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
---

# 3.6 No rotation after login

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

Detect authentication flows that do not rotate the primary session identifier after login or privilege elevation. The runner cares because session identifiers should change when authentication state changes; otherwise an exposed anonymous or low-privilege token can become an authenticated session.

## Inputs

The runner receives a shared `ScanTarget` and writes shared `Evidence` records. This stub does not redefine either type.

Required inputs:

* `target`: shared `ScanTarget`.
* `base_url`: normalized target origin from `ScanTarget`.
* `http_client`: shared HTTP client with isolated cookie-jar support.
* `scanner_config`: stub-specific knobs listed below.

Required for confirmed testing:

* `test_account`: scoped credentials from fixture config, scan config, or approved credential store.
* `login_flow`: discovered login form/API metadata, or a fixture adapter that knows how to authenticate safely.

Optional inputs:

* `step_up_flow`: known MFA, sudo-mode, admin-switch, or privilege-elevation flow supplied by fixture or scan config.
* `logout_flow`: safe logout URL or API for cleanup.
* `known_session_cookie_names`: session cookie names from prior cookie checks.
* `csrf_extractor`: shared helper for login forms with CSRF tokens.

Config knobs:

| Name | Default | Purpose |
| ---- | ------: | ------- |
| `enabled` | `true` | Allows this stub to run. |
| `allow_login_submission` | `false` | Must be explicitly enabled with scoped credentials. |
| `allow_step_up_submission` | `false` | Disabled unless a fixture or program explicitly scopes the flow. |
| `max_login_attempts` | `1` | Prevents account lockout and noisy auth logs. |
| `max_step_up_attempts` | `1` | Prevents repeated sensitive-flow submissions. |
| `request_timeout_ms` | `10000` | Per-request timeout. |
| `follow_redirects` | `false` | Keep rotation redirects visible as evidence. |
| `cleanup_logout` | `true` | Attempt safe logout cleanup when known. |
| `redact_cookie_values` | `true` | Cookie values must be redacted before logs and findings. |

## Detection logic

Detection is deterministic and compares session cookie fingerprints across authentication state transitions.

### 1. Establish anonymous baseline

Use a fresh isolated client and cookie jar.

1. `GET` the login page or application landing page.
2. Capture `Set-Cookie` evidence.
3. Identify likely session cookies by name, domain, path, and context.
4. Store secure fingerprints, never raw cookie values.

If no anonymous session cookie exists, continue. The app may create the session only after login, which is acceptable.

### 2. Submit one controlled login

Only run when `allow_login_submission=true` and scoped credentials are available.

1. Refresh login form metadata if CSRF or hidden fields are present.
2. Submit exactly one valid login request.
3. Capture login response status, redirect behavior, and all `Set-Cookie` headers.
4. Confirm authentication through a fixture oracle, expected redirect, or safe authenticated marker.
5. Compare session cookie fingerprints before and after login.

Rotation is present when:

* The main session cookie value changes.
* The anonymous session cookie is expired and a new authenticated session cookie is issued.
* The authenticated session uses a different cookie name only if the old anonymous cookie is no longer accepted as the auth-bearing session.

No rotation is present when:

* The same session cookie value exists before and after successful login.
* Only non-auth cookies rotate while the primary session/auth cookie remains stable.
* The login response creates authenticated state without replacing or expiring the pre-login session cookie.

### 3. Optional privilege transition check

Only run when `allow_step_up_submission=true` and `step_up_flow` is explicitly configured.

Examples:

* Completing MFA after password login.
* Entering sudo-mode for account settings.
* Switching from normal user workspace to admin console.
* Accepting an organization role elevation in a fixture.

For each configured step-up flow, compare the primary session identifier before and after the transition. A privileged session should rotate or issue a distinct, narrower privilege token.

Do not discover or force privilege transitions in this spec.

### 4. Status and confidence

| Condition | Status | Confidence |
| --------- | ------ | ---------- |
| Successful login keeps the same primary session cookie fingerprint. | `confirmed` | `high` |
| Configured step-up flow keeps the same primary session cookie fingerprint. | `confirmed` | `high` |
| Login succeeds but no primary session cookie can be identified. | `candidate` | `low` |
| Login rotates or replaces the primary session cookie. | `rejected` | `high` |
| Test aborted because credentials are missing, CAPTCHA appears, rate limit triggers, MFA is unconfigured, or safety is uncertain. | `stale` | `low` |

Do not mark a finding confirmed without proof that the login or step-up transition succeeded.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Stub-specific types: `NoRotationAfterLoginSignature`, `NoRotationAfterLoginFinding`.

### `NoRotationAfterLoginSignature`

```ts
export interface NoRotationAfterLoginSignature {
  signature_id: string;
  transition_kind: "anonymous_to_authenticated" | "authenticated_to_step_up";
  transition_url: string;
  transition_method: "GET" | "POST";
  session_cookie_name: string;
  session_cookie_domain?: string;
  session_cookie_path?: string;
  requires_valid_credentials: true;
  confidence: "low" | "medium" | "high";
  enabled: boolean;
  created_at: string;
  updated_at: string;
}
```

### `NoRotationAfterLoginFinding`

```ts
export interface NoRotationAfterLoginFinding {
  finding_id: string;
  target_id: string;
  evidence_ids: string[];

  transition_kind: "anonymous_to_authenticated" | "authenticated_to_step_up";
  transition_url: string;
  transition_method: "GET" | "POST";
  transition_succeeded: boolean;

  session_cookie_name: string;
  session_cookie_domain?: string;
  session_cookie_path?: string;
  before_cookie_fingerprint?: string;
  after_cookie_fingerprint?: string;

  rotation_result:
    | "rotated"
    | "reused"
    | "expired_and_replaced"
    | "not_observable"
    | "aborted";

  comparison: {
    before_observed: boolean;
    after_observed: boolean;
    cookie_replaced: boolean;
    cookie_expired: boolean;
    privilege_level_changed: boolean;
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

* Baseline cookie evidence with redacted values.
* Login or step-up request metadata with secrets omitted.
* Post-transition cookie evidence with redacted values.
* Authentication or privilege-transition success evidence.
* Optional cleanup/logout evidence when cleanup is performed.

Recommended remediation:

* Regenerate the server-side session identifier immediately after login.
* Regenerate or narrow privilege tokens after MFA, sudo-mode, admin entry, or role elevation.
* Expire the anonymous or lower-privilege session identifier during the transition.
* Ensure downstream caches, WebSocket sessions, and API tokens observe the new authenticated session state.

## Safety

This check is active because it may submit a valid login or explicitly configured step-up request.

Allowed:

* `GET` login page and safe authenticated pages.
* One valid login request when `allow_login_submission=true`.
* One configured step-up request when `allow_step_up_submission=true`.
* One safe logout cleanup request when known.

Not allowed:

* Password guessing.
* Username guessing.
* Discovering or forcing step-up flows.
* More than the configured login or step-up attempt budget.
* Testing real user accounts not explicitly scoped.
* Bypassing MFA, CAPTCHA, WAF, lockout, or rate limits.
* Continuing after `429`, lockout wording, abuse detection, or CAPTCHA.
* Accessing sensitive user data after login beyond the minimum proof of authenticated state.
* Reusing captured session cookies outside the isolated test client.

PII and secrets:

* Never log passwords, MFA codes, recovery codes, or CSRF tokens.
* Redact usernames/emails unless they are fixture-only synthetic identifiers.
* Never log raw cookie values.
* Store cookie fingerprints only with the project-approved secret hashing helper.
* Do not send auth or cookie evidence to AI.

AI involvement: `None`.

There is no deterministic gap that requires AI. State-transition comparison and cookie fingerprinting are deterministic.

## Pass/fail check

A coding agent implementation passes when these assertions hold.

Positive assertions:

* It accepts a shared `ScanTarget` and writes shared `Evidence`.
* It does not redefine shared `ScanTarget` or `Evidence`.
* It uses an isolated cookie jar for each lifecycle test.
* It captures pre-transition and post-transition cookie fingerprints.
* It submits at most one valid login when explicitly enabled and scoped credentials exist.
* It refreshes CSRF or hidden fields before login when required.
* It proves transition success before classifying rotation.
* It compares the primary session cookie by name, domain, and path.
* It creates a `confirmed`, `high` finding when a successful login keeps the same primary session cookie value.
* It creates a `rejected`, `high` result or no vulnerability finding when the session cookie rotates.
* It marks the test `stale`, `low` when credentials, CAPTCHA, rate limits, MFA, or unsafe side effects block testing.
* It redacts credentials, CSRF tokens, and cookie values.
* It links each finding to at least one `Evidence` record.

Negative assertions:

* It must not submit guessed usernames or passwords.
* It must not perform more than the configured attempt budget.
* It must not use real accounts unless explicitly scoped.
* It must not bypass MFA, CAPTCHA, WAF, rate limits, or lockout.
* It must not discover or force privilege transitions.
* It must not continue testing after `429`, lockout, or abuse detection.
* It must not reuse captured cookies outside the isolated test client.
* It must not store raw passwords, MFA codes, CSRF tokens, or cookie values.
* It must not send auth evidence to an LLM.
* It must not mark a finding confirmed without proof of successful transition.

## Test fixtures

Use the synthetic fixture slug: `session-lifecycle`.

Required fixture routes:

| Route | Behavior | Expected result |
| ----- | -------- | --------------- |
| `/rotation/login-vulnerable` | Sets anonymous `sid`, accepts login, keeps same `sid`. | `confirmed`, `high` |
| `/rotation/login-safe` | Sets anonymous `sid`, accepts login, replaces `sid`. | `rejected`, `high` or no finding |
| `/rotation/login-no-pre-cookie` | No anonymous session; creates new session only after login. | no vulnerability finding |
| `/rotation/login-csrf` | Login form uses per-request CSRF token and vulnerable/no-rotation behavior. | Runner refreshes token and detects correctly. |
| `/rotation/login-captcha` | Shows CAPTCHA or abuse marker before submit. | `stale`, `low`; runner stops. |
| `/rotation/step-up-vulnerable` | Fixture step-up succeeds without rotating session. | `confirmed`, `high` when step-up enabled. |
| `/rotation/step-up-safe` | Fixture step-up rotates or issues distinct privilege token. | `rejected`, `high` when step-up enabled. |

Seeded fixture account:

* Username: `alice@example.invalid`
* Password: fixture-provided secret
* Step-up secret: fixture-provided synthetic value, never a real MFA code
* Account state must reset between tests.

Compatibility fixtures:

* `dvwa` may be used for exploratory adapter work if deterministic login and resettable state are available.
* `juice-shop` and `webgoat` may be used only as secondary compatibility checks, not primary acceptance fixtures.

## Acceptance criteria

The implementation is acceptable when:

* The check is deterministic against the fixture.
* It uses isolated clients and cookie jars.
* It performs no login unless `allow_login_submission=true`.
* It performs no step-up request unless `allow_step_up_submission=true`.
* It completes within the configured request, login, and step-up budgets.
* It handles missing login forms, missing credentials, invalid CSRF, redirects, TLS failures, timeouts, and connection errors gracefully.
* It stops on CAPTCHA, MFA challenge without configured fixture secret, lockout, WAF block, abuse detection, or `429`.
* It redacts credentials, CSRF tokens, authorization headers, MFA values, and cookie values.
* It stores findings with at least one evidence ID.
* It reports `confirmed`, `rejected`, and `stale` statuses correctly.
* It defines only `NoRotationAfterLoginSignature` and `NoRotationAfterLoginFinding` as stub-specific types.
* Unit tests cover login-flow extraction, CSRF refresh, transition success detection, cookie fingerprinting, rotation comparison, step-up gating, cleanup, redaction, safety aborts, and negative assertions.
* Fixture tests cover vulnerable login, safe login, no pre-login cookie, CSRF login, CAPTCHA abort, vulnerable step-up, and safe step-up.
* AI is not called.
