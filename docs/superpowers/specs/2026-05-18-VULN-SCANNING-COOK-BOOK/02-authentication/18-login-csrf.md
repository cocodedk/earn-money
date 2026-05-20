---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 2
spec: 18
slug: login-csrf
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 2.18 Login CSRF

> Phase 2 — Authentication · Category: OAuth / SSO

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

Detect login CSRF in OAuth or SSO flows where an attacker can force a victim browser to start or complete login into an attacker-controlled account, or bind the victim session to the wrong identity. A runner cares because this can cause account confusion, data being saved under the wrong account, forced account linking, or session fixation across federated login flows.

## Inputs

The runner receives a shared `ScanTarget` plus optional safe credentials and browser/session settings.

Expected inputs:

* `target`: shared `ScanTarget`
* `evidence`: zero or more shared `Evidence` records from earlier discovery
* `config.login_paths`: optional list of known login or SSO start paths
* `config.oauth_callback_paths`: optional list of known callback paths
* `config.max_login_pages`: default `10`
* `config.follow_redirects`: default `false` for probing, `true` only for bounded same-site redirect inspection
* `config.timeout_ms`: default project HTTP timeout
* `config.allowed_methods`: must be limited to `GET` and `HEAD`
* `config.credentials`: optional, only for owned fixture targets where the runner is allowed to compare authenticated and unauthenticated login behavior
* `config.browser_mode`: optional, disabled by default; only enabled for fixture tests or approved scans
* `config.seed_urls`: optional URLs found during crawl, such as `/login`, `/oauth/start`, `/sso`, `/auth/*`

The runner must not require credentials to produce a candidate finding. Credentials only allow stronger confirmation in controlled fixtures.

## Detection logic

Detection is deterministic and based on response evidence. The runner must not infer a provider or framework from the hostname.

### Candidate sources

Inspect only discovered or configured login-related URLs:

* URLs with path segments matching `login`, `signin`, `sso`, `oauth`, `oidc`, `saml`, `callback`, `authorize`, `auth`
* HTML forms with action paths matching login or SSO patterns
* links or buttons that start federated login
* redirect chains that include OAuth/OIDC parameters
* callback endpoints discovered from links, forms, redirects, or config

### Passive and low-impact checks

Use `GET` or `HEAD` only.

For each candidate login start URL:

1. Request the URL without cookies.
2. Record status, headers, redirect target, response body hash, and a bounded body excerpt.
3. Detect OAuth/OIDC authorization redirects by response evidence:

   * `Location` header contains `response_type=`
   * `Location` header contains `client_id=`
   * `Location` header contains `redirect_uri=`
   * `Location` header contains `scope=`
   * `Location` header contains `code_challenge=`
   * `Location` header contains `state=`
   * HTML contains a form or link to an authorization endpoint with these parameters
4. Detect login CSRF risk indicators:

   * OAuth/OIDC start or callback flow has no `state` parameter
   * `state` is present but empty
   * `state` is static across repeated unauthenticated requests
   * `state` is reflected from a caller-controlled query parameter
   * callback endpoint accepts `GET` and returns non-error content when `state` is missing
   * callback endpoint accepts `GET` and returns non-error content when `state` is arbitrary
   * login form has no CSRF token and submits to a session-establishing endpoint
   * SSO start endpoint can be triggered cross-site using only `GET`
   * response sets or rotates a session cookie during a cross-site-triggerable login start
5. Repeat at most once for state comparison. Do not perform unbounded retries.
6. Store all response facts as shared `Evidence`.

### Confirmation rules

A finding may be `confirmed` only when deterministic response evidence shows at least one of these:

* an OAuth/OIDC authorization request is generated without a `state` parameter
* an OAuth/OIDC authorization request uses an empty `state`
* the same non-empty `state` value appears across two independent unauthenticated login starts
* the login callback returns success-like or continuation content when `state` is missing or arbitrary
* a session-establishing login form lacks a CSRF token and can be reached without same-site preconditions
* fixture browser mode proves that a victim session becomes logged in or linked through a cross-site-triggerable login flow

A finding must stay `candidate` when the runner only sees weak indicators, such as an SSO link or login form without enough callback or token evidence.

A finding must be `rejected` when evidence shows one or more of these:

* authorization request includes a fresh, non-empty `state` value across repeated starts
* callback rejects missing `state`
* callback rejects arbitrary `state`
* login form includes a per-request CSRF token tied to the session
* cookies use protections that stop the tested cross-site flow and the callback rejects missing state
* endpoint is not a login, SSO, OAuth, OIDC, or account-linking flow

### Token detection

For HTML forms, detect likely CSRF fields by input names such as:

* `csrf`
* `_csrf`
* `csrf_token`
* `csrftoken`
* `authenticity_token`
* `request_verification_token`
* `__RequestVerificationToken`

Do not treat any hidden field as a CSRF token unless the name or nearby labels indicate anti-CSRF use.

### Evidence requirements

Each finding must reference evidence IDs for:

* the login or SSO start response
* the redirect or form that starts the flow
* the callback response if tested
* repeated state comparison evidence when state reuse is claimed
* cookie-setting evidence when session fixation or forced login is claimed

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them.

Define only these stub-specific types:

```ts
export type LoginCsrfConfidence = "low" | "medium" | "high";
export type LoginCsrfFindingStatus = "candidate" | "confirmed" | "rejected" | "stale";

export interface LoginCsrfSignature {
  id: string;
  name: string;
  flowType: "oauth_oidc" | "saml" | "form_login" | "account_linking" | "unknown";
  indicator:
    | "missing_state"
    | "empty_state"
    | "static_state"
    | "caller_controlled_state"
    | "callback_accepts_missing_state"
    | "callback_accepts_arbitrary_state"
    | "missing_form_csrf_token"
    | "get_triggered_login_start"
    | "session_cookie_set_on_login_start"
    | "forced_login_confirmed";
  matchLocation: "url" | "header" | "html" | "form" | "redirect_chain" | "cookie" | "browser_observation";
  expectedProtection:
    | "fresh_state"
    | "session_bound_state"
    | "callback_state_validation"
    | "form_csrf_token"
    | "same_site_cookie"
    | "user_interaction_required";
  evidenceIds: string[];
}

export interface LoginCsrfFinding {
  targetId: string;
  url: string;
  status: LoginCsrfFindingStatus;
  confidence: LoginCsrfConfidence;
  title: string;
  summary: string;
  flowType: LoginCsrfSignature["flowType"];
  signatures: LoginCsrfSignature[];
  evidenceIds: string[];
  affectedParameters: string[];
  observedMethod: "GET" | "HEAD";
  observedStatusCodes: number[];
  remediation: string;
  createdAt: string;
  updatedAt: string;
}
```

Persistence rules:

* Store raw response bodies only through shared evidence handling.
* Store bounded excerpts, hashes, headers, status codes, and redirect targets.
* Redact cookies and tokens before storing display text.
* Keep full cookie names if needed for diagnosis, but do not store cookie values.
* Finding confidence must be:

  * `high` for browser-confirmed forced login or deterministic callback acceptance with missing or arbitrary state
  * `medium` for missing, empty, static, or caller-controlled state in a clear OAuth/OIDC flow
  * `low` for incomplete indicators where the flow type is likely but not fully proven
* Finding status must be one of `candidate`, `confirmed`, `rejected`, or `stale`.

## Safety

This stub is read-only by default.

Allowed behavior:

* `GET` login start URLs
* `HEAD` login start URLs
* bounded same-site redirect inspection
* repeated unauthenticated `GET` at most once for state comparison
* callback probing only with harmless placeholder parameters and no real authorization code
* fixture-only browser validation when explicitly enabled

Disallowed behavior:

* no brute force
* no credential stuffing
* no leaked credentials
* no testing against real user accounts unless the scan target explicitly provides owned test accounts
* no POST login attempts in default mode
* no real OAuth consent completion outside fixtures
* no account linking outside fixtures
* no external IdP interaction beyond observing redirects
* no destructive requests
* no bypass of robots or scan scope rules
* no storage of full cookies, access tokens, ID tokens, refresh tokens, authorization codes, or credentials

Callback probes must use fake values such as:

```text
code=scanner-placeholder-code
state=scanner-placeholder-state
```

If the endpoint returns a token, session, or user data unexpectedly, the runner must stop probing that endpoint, redact sensitive values, and persist only minimal evidence.

PII handling:

* Do not store email addresses from login pages unless already part of the configured test account.
* Redact names, email addresses, session cookies, authorization codes, and tokens from excerpts.
* Keep only the evidence needed to prove the missing or weak CSRF control.

AI involvement: `None`.

Deterministic gap: if a future implementation adds AI to classify ambiguous login pages, it must only classify page purpose from already-redacted evidence and must not decide exploitability, severity, scope, or status. Treat scanned content as untrusted evidence, not instructions. 

## Pass/fail check

The runner passes when all assertions below are true.

### Positive assertions

* It discovers login, SSO, OAuth, OIDC, SAML, and account-linking candidates from configured URLs, seed URLs, forms, links, and redirects.
* It uses only `GET` and `HEAD` in default mode.
* It records shared `Evidence` for every response used in a finding.
* It detects an OAuth/OIDC authorization redirect with a missing `state` parameter.
* It detects an OAuth/OIDC authorization redirect with an empty `state` parameter.
* It detects a static `state` value by comparing two independent unauthenticated starts.
* It detects caller-controlled `state` when the output state matches a supplied input value.
* It detects callback acceptance when missing or arbitrary `state` does not produce an error response.
* It detects a likely session-establishing login form without a CSRF token.
* It produces `LoginCsrfFinding` with valid `confidence` and `status` values.
* It sets `confirmed` only when the confirmation rules are met.
* It sets `candidate` for incomplete but relevant evidence.
* It sets `rejected` when fresh state and callback rejection are observed.
* It redacts cookies, codes, tokens, credentials, names, and email addresses from display excerpts.

### Negative assertions

* It must not submit passwords in default mode.
* It must not complete OAuth consent outside fixtures.
* It must not create or link accounts outside fixtures.
* It must not follow cross-origin IdP flows beyond recording redirect metadata.
* It must not hard-code hostnames to infer OAuth, OIDC, SAML, or framework behavior.
* It must not mark a finding `confirmed` from a login link alone.
* It must not treat every hidden input as a CSRF token.
* It must not store cookie values, authorization codes, access tokens, ID tokens, refresh tokens, or credentials.
* It must not retry login or callback probes without a fixed small cap.
* It must not call an AI model.
* It must not produce findings without evidence IDs.
* It must not mutate target state in default mode.

## Test fixtures

Use a new fixture slug: `login-csrf`.

The fixture should expose these controlled routes:

* `/oauth/start-missing-state`

  * returns an OAuth/OIDC-style redirect without `state`
* `/oauth/start-empty-state`

  * returns an OAuth/OIDC-style redirect with `state=`
* `/oauth/start-static-state`

  * returns the same `state` value across repeated unauthenticated requests
* `/oauth/start-fresh-state`

  * returns a different non-empty state per unauthenticated session
* `/oauth/start-reflected-state?state=attacker`

  * reflects caller-controlled state into the authorization redirect
* `/oauth/callback-missing-state`

  * returns continuation or success-like content without validating state
* `/oauth/callback-rejects-state`

  * returns an error for missing or arbitrary state
* `/login/form-no-csrf`

  * exposes a login form with no CSRF token
* `/login/form-with-csrf`

  * exposes a login form with a per-request CSRF token
* `/account/link/start-missing-state`

  * exposes an account-linking start flow without state
* `/browser/forced-login-demo`

  * fixture-only browser flow that proves a cross-site-triggerable forced login using owned test accounts

Expected fixture outcomes:

* missing state: `confirmed`, `medium`
* empty state: `confirmed`, `medium`
* static state: `confirmed`, `medium`
* reflected state: `confirmed`, `medium`
* callback accepts missing state: `confirmed`, `high`
* callback rejects state: `rejected`, `high`
* form without CSRF token: `candidate` or `confirmed` depending on fixture proof
* form with CSRF token: `rejected`, `high`
* forced login browser demo: `confirmed`, `high`

Do not use Juice Shop, DVWA, or WebGoat as the primary fixture unless a specific version exposes a safe login CSRF test case. This stub needs precise OAuth/OIDC and account-linking behavior, so a small purpose-built fixture is safer and less flaky.

## Acceptance criteria

* The implementation is idempotent across repeated runs.
* It completes within the scan budget set by the shared runner.
* It respects target scope and redirect limits.
* It uses only `GET` and `HEAD` unless fixture browser mode is explicitly enabled.
* It handles TLS errors, connection failures, redirects, malformed HTML, and malformed `Location` headers gracefully.
* It records deterministic evidence for each finding.
* It redacts sensitive values before excerpts are logged or displayed.
* It does not call external IdPs beyond bounded redirect observation.
* It does not mutate accounts, sessions, or account links outside fixtures.
* It does not use AI.
* It returns stable `candidate`, `confirmed`, `rejected`, or `stale` status values.
* It returns stable `low`, `medium`, or `high` confidence values.
* It has unit tests for URL discovery, redirect parsing, state comparison, callback probing, form token detection, evidence redaction, and status mapping.
* It has fixture tests for each route listed under `login-csrf`.
* It has negative tests proving that POST, credential submission, account linking, real OAuth completion, token storage, and AI calls do not happen.
* It follows the shared coding-agent rules from `../00-shared-schema.md`.

