---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 2
spec: 4
slug: weak-rate-limiting
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 2.4 Weak rate limiting

> Phase 2 — Authentication · Category: Weak login behavior

## Purpose

Detect login endpoints that allow repeated failed authentication attempts without any visible throttling, temporary blocking, CAPTCHA/challenge, rate-limit headers, or retry guidance. A runner cares because weak login rate limiting makes password guessing cheaper, even when account lockout is tested separately.

## Inputs

The runner receives a shared `ScanTarget` plus an authentication probe configuration.

Required inputs:

* `target`: shared `ScanTarget`.
* `login_url`: absolute or target-relative URL for the login endpoint, or a discovered login form URL from an earlier authentication-discovery step.
* `method`: usually `POST`; default is taken from the discovered form or supplied login flow.
* `username_field`: request field name for the username, email, or login identifier.
* `password_field`: request field name for the password.
* `failure_detector`: deterministic matcher for failed-login responses. This may use status code, stable body substring, redirect target, content hash, or configured failure marker.
* `synthetic_username`: scanner-generated nonexistent username, unless a dedicated test account is explicitly supplied.
* `synthetic_password`: scanner-generated invalid password.

Optional inputs:

* `csrf_field`: CSRF field name when the login form requires a token.
* `csrf_source_url`: URL to fetch a fresh CSRF token before each attempt.
* `headers`: extra headers needed for the login flow, excluding secrets unless explicitly allowed by scope.
* `cookies`: scoped cookies needed to reach the login page.
* `max_attempts`: total failed-login attempts allowed for this probe. Default: `6`. Hard maximum: `10`.
* `policy_max_failures_without_throttle`: expected maximum number of failures before throttling. Default: `5`.
* `attempt_window_seconds`: maximum time window for the attempts. Default: `60`.
* `delay_between_attempts_ms`: delay between attempts. Default: `250`.
* `timeout_seconds`: per-request timeout. Default follows the shared runner timeout.
* `follow_redirects`: default `false`, unless the discovered login flow requires one redirect to observe failure.
* `allow_dedicated_test_account`: default `false`.
* `test_account_username`: optional username for a dedicated scanner-owned account. Must not be a real user account.
* `stop_on_success`: default `true`.
* `stop_on_throttle`: default `true`.
* `evidence_body_bytes`: maximum response body bytes stored per attempt. Default follows shared evidence limits.

Credential rules:

* Use a nonexistent scanner-generated identity by default.
* Use a dedicated scanner-owned test account only when the operator configured it for rate-limit testing.
* Never test real user accounts.
* Never use leaked passwords, password lists, credential stuffing data, or many password variants.
* Never perform distributed, parallel, or long-running login attempts.

## Detection logic

Detection is deterministic and bounded.

### 1. Resolve the login flow

The runner uses the supplied login flow first. If no explicit flow is supplied, it may use a previously discovered login form from the same `ScanTarget`.

A login endpoint is eligible only when the runner can determine:

* request method
* submit URL
* username field
* password field
* failed-login response marker or stable failure fingerprint

If the endpoint cannot be identified as a login flow, the check returns `rejected` with low confidence and does not send failed-login attempts.

### 2. Build one invalid credential pair

Default credential pair:

* username: scanner-generated nonexistent value, such as `scanner-rate-limit-<run_id>@invalid.example`
* password: scanner-generated high-entropy invalid value

The same pair is reused for all attempts in the probe. This avoids password spraying and keeps the check focused on request throttling, not password guessing.

If a dedicated scanner-owned test account is configured, the runner may use that username with an invalid password. This must be explicitly enabled.

### 3. Send a baseline failed login

The runner sends one failed-login request and records:

* request method
* endpoint URL
* status code
* redirect target, if any
* selected headers
* normalized response body hash
* failure marker result
* response time
* CSRF refresh behavior, if needed

If the baseline response looks like a successful login, the runner stops immediately and marks the result `rejected`. The runner must not continue after unexpected authentication success.

### 4. Send a small bounded sequence

The runner sends additional failed-login attempts until one of these happens:

* `max_attempts` is reached
* a throttle signal is observed
* a CAPTCHA or challenge is observed
* a lockout or temporary block signal is observed
* an unexpected success is observed
* the request budget is exhausted
* a network or TLS error prevents safe classification

For each attempt, the runner records compact `Evidence`. Full response bodies are not stored unless the shared evidence policy allows it.

If CSRF tokens are required, the runner fetches a fresh token before each attempt. CSRF refresh requests count against the runner request budget but not against `max_attempts`.

### 5. Detect throttle signals

The runner treats these as rate-limit or blocking indicators:

* HTTP `429`
* HTTP `403`, `423`, or `503` with a rate-limit, temporary-block, lockout, or retry message
* `Retry-After` header
* standard or common rate-limit headers, including:

  * `RateLimit-Limit`
  * `RateLimit-Remaining`
  * `RateLimit-Reset`
  * `X-RateLimit-Limit`
  * `X-RateLimit-Remaining`
  * `X-RateLimit-Reset`
* body text matching known throttle phrases, case-insensitive:

  * `too many attempts`
  * `too many login attempts`
  * `rate limit`
  * `try again later`
  * `temporarily blocked`
  * `temporarily locked`
  * `slow down`
  * `captcha required`
  * `verification required`
* redirect to a CAPTCHA, challenge, blocked, or recovery page
* response body fingerprint changing from normal login failure to a stable throttle/challenge page

Latency alone is not enough to confirm rate limiting. The runner may store latency as supporting evidence, but it must not classify a target as throttled only because responses became slower.

### 6. Classify the result

The runner compares observed attempts with `policy_max_failures_without_throttle`.

Confirmed weak rate limiting:

* login flow is confirmed
* at least `policy_max_failures_without_throttle + 1` failed attempts were sent
* all attempts produced ordinary failed-login responses
* no throttle, CAPTCHA, temporary block, retry guidance, or lockout signal was observed
* no rate-limit headers were observed
* request count stayed within the safe cap

Candidate weak rate limiting:

* the endpoint is likely a login flow, but evidence is incomplete
* or fewer attempts were allowed by the scan budget
* or failure detection is based only on weak fingerprints
* or the policy threshold is not configured and the runner only knows that no throttle was seen within the safe probe budget

Rejected:

* throttle, challenge, CAPTCHA, temporary block, or retry guidance was observed within the policy threshold
* or the endpoint was not a confirmed login flow
* or baseline authentication unexpectedly succeeded
* or safety controls stopped the probe before meaningful evidence was collected

Stale:

* previous evidence exists, but the endpoint, form fields, response fingerprints, or target URL changed before revalidation.

Confidence:

* `high`: confirmed login flow, deterministic failure marker, at least `policy_max_failures_without_throttle + 1` attempts, no throttle signals.
* `medium`: confirmed login flow, stable failure fingerprints, bounded attempts completed, but policy threshold or failure marker is less explicit.
* `low`: discovered endpoint is uncertain, request budget ended early, network errors affected the result, or only partial evidence exists.

## Persistence

Use the shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them.

Define only stub-specific types:

```ts
export type WeakRateLimitingCredentialSource =
  | "scanner_generated_invalid"
  | "dedicated_test_account_invalid_password";

export type WeakRateLimitingThrottleSignal =
  | "http_429"
  | "retry_after_header"
  | "rate_limit_header"
  | "temporary_block_status"
  | "temporary_block_body"
  | "captcha_or_challenge"
  | "lockout_signal"
  | "throttle_redirect"
  | "failure_fingerprint_changed_to_throttle";

export type WeakRateLimitingSignature = {
  login_url: string;
  method: string;
  username_field: string;
  password_field: string;
  credential_source: WeakRateLimitingCredentialSource;

  attempts_sent: number;
  policy_max_failures_without_throttle: number;
  attempt_window_seconds: number;
  delay_between_attempts_ms: number;

  observed_status_codes: number[];
  observed_failure_fingerprints: string[];
  observed_redirect_targets: string[];

  rate_limit_headers_seen: string[];
  throttle_observed: boolean;
  throttle_signals: WeakRateLimitingThrottleSignal[];

  captcha_or_challenge_observed: boolean;
  lockout_signal_observed: boolean;
  unexpected_success_observed: boolean;

  exceeded_policy_threshold_without_throttle: boolean;
  failure_detector_name: string;
  failure_detector_matched_attempts: number;

  request_budget_exhausted: boolean;
  stopped_reason:
    | "max_attempts_reached"
    | "throttle_observed"
    | "captcha_or_challenge_observed"
    | "lockout_signal_observed"
    | "unexpected_success"
    | "request_budget_exhausted"
    | "network_error"
    | "tls_error"
    | "not_login_flow";
};

export type WeakRateLimitingFinding = {
  id: string;
  target: ScanTarget;
  evidence: Evidence[];
  signature: WeakRateLimitingSignature;

  status: "candidate" | "confirmed" | "rejected" | "stale";
  confidence: "low" | "medium" | "high";

  title: string;
  summary: string;
  affected_endpoint: string;
  impact: string;
  remediation: string;

  created_at: string;
  updated_at: string;
};
```

Persistence rules:

* Store one finding per normalized login endpoint and credential-source mode.
* Store compact evidence for each attempt.
* Store response body hashes and short redacted snippets, not full bodies by default.
* Redact usernames when they are operator-supplied.
* Never persist passwords.
* Never persist cookies, bearer tokens, CSRF tokens, session IDs, or full request headers.
* Link all finding claims to `Evidence` IDs.
* If a new scan observes throttling where a previous scan did not, mark the previous finding `stale` or update it to `rejected`, following shared stale-finding rules.

## Safety

This check sends failed login requests, so it is state-changing from the target’s point of view even though it does not change application data intentionally.

Safety rules:

* Run only when authentication testing is in scope.
* Use the supplied or discovered login endpoint only.
* Do not crawl for extra login endpoints inside this stub.
* Do not brute force.
* Do not password spray.
* Do not use leaked credential lists.
* Do not try many usernames.
* Do not try many passwords.
* Do not test real user accounts.
* Do not continue after unexpected authentication success.
* Do not continue after a throttle, CAPTCHA, challenge, lockout, or temporary block is observed.
* Do not bypass CAPTCHA, MFA, device checks, IP blocks, or challenge pages.
* Do not use parallel attempts.
* Do not distribute attempts across IPs, sessions, proxies, or user agents.
* Do not increase the request count beyond `max_attempts`.
* Do not retry failed requests blindly.
* Do not infer account validity from response differences in this stub. Username enumeration belongs to spec `2.1`.
* Do not test account lockout state in this stub. Missing lockout belongs to spec `2.3`.

HTTP method discipline:

* Use the login form’s configured method.
* Default to `POST`.
* Do not use unsafe methods other than the configured login submit method.
* CSRF-token refresh may use `GET` only against the login page or configured token source.
* Do not call password reset, registration, MFA, profile, or admin endpoints.

Payload restrictions:

* One username.
* One invalid password.
* Small fixed number of attempts.
* Normal browser-like form submission only.
* No SQL, XSS, command, path, template, or deserialization payloads.

PII handling:

* Prefer scanner-generated nonexistent usernames.
* Redact operator-supplied usernames in logs and persisted snippets.
* Never log passwords.
* Never store session cookies or CSRF token values.
* Store only the minimum evidence needed to prove whether throttling appeared.

AI involvement:

* `None`.

Deterministic gap:

* AI must not decide whether rate limiting is weak.
* AI must not classify response bodies.
* If future work adds body-language clustering or report prose, it must use already persisted deterministic evidence only and must not affect finding status.

## Pass/fail check

The implementation passes when these assertions are true.

Positive assertions:

* Given a fixture login endpoint that never throttles, the runner sends no more than the configured attempt cap.
* Given `policy_max_failures_without_throttle = 5` and `max_attempts = 6`, six ordinary failed-login responses produce a `confirmed` finding.
* The finding uses confidence `high` when the login flow and failed-login marker are deterministic.
* The finding uses confidence `medium` or `low` when the endpoint or failure marker is uncertain.
* Each attempt creates compact `Evidence`.
* The persisted `WeakRateLimitingSignature` includes attempt count, status codes, response fingerprints, observed headers, throttle signals, and stop reason.
* A `429` response with `Retry-After` produces `rejected` or no active weak-rate-limiting finding.
* A CAPTCHA or challenge response stops the probe.
* A temporary block message stops the probe.
* An unexpected successful login stops the probe and does not create a weak-rate-limiting finding.
* CSRF-protected forms are handled by refreshing the token safely before each failed attempt.
* TLS and network failures are reported as inconclusive without retry storms.
* The result is reproducible for the same fixture and config.

Negative assertions:

* The runner must not send more than `max_attempts` failed-login submissions.
* The runner must not test multiple usernames.
* The runner must not test multiple passwords.
* The runner must not use leaked password lists.
* The runner must not use real user accounts.
* The runner must not continue after observing throttling.
* The runner must not continue after CAPTCHA, challenge, lockout, temporary block, or unexpected success.
* The runner must not classify latency alone as throttling.
* The runner must not classify missing rate-limit headers alone as a confirmed vulnerability unless the failed-attempt threshold was exceeded without another throttle signal.
* The runner must not hard-code hostname, product, framework, or expected behavior.
* The runner must not persist passwords, cookies, CSRF tokens, bearer tokens, or full sensitive request headers.
* The runner must not store full response bodies by default.
* The runner must not call password reset, registration, MFA, profile, or admin endpoints.
* The runner must not use AI for detection or classification.

## Test fixtures

Primary fixture: `weak-rate-limiting`.

The fixture should expose two deterministic login endpoints:

* `/auth/login-unlimited`

  * accepts `POST`
  * always returns a normal failed-login response for invalid credentials
  * does not return `429`
  * does not return `Retry-After`
  * does not return rate-limit headers
  * expected scanner result: `confirmed`

* `/auth/login-throttled`

  * accepts `POST`
  * returns normal failed-login responses for the first few invalid attempts
  * returns `429` plus `Retry-After` after the configured threshold
  * expected scanner result: `rejected`

Optional fixture endpoint:

* `/auth/login-csrf-throttled`

  * exposes a `GET` login form with a CSRF token
  * requires a fresh token for each `POST`
  * throttles after the configured threshold
  * expected scanner result: `rejected`
  * verifies that CSRF refresh does not become an unbounded retry loop

Do not use public internet targets for tests.

`juice-shop`, `dvwa`, and `webgoat` may be used only as observational integration fixtures if they are already part of the local test environment. They must not be the primary pass/fail source for this stub because their rate-limit behavior may change by version or configuration.

## Acceptance criteria

The stub is acceptable when:

* It uses shared `ScanTarget` and `Evidence`.
* It defines only `WeakRateLimitingSignature` and `WeakRateLimitingFinding` as stub-specific persistence types.
* It is deterministic and uses no AI.
* It sends a small, bounded number of failed-login attempts.
* It uses one invalid credential pair.
* It never uses real user accounts, leaked passwords, credential lists, or brute force.
* It distinguishes weak rate limiting from username enumeration and missing account lockout.
* It stops immediately on throttle, CAPTCHA, challenge, lockout, temporary block, unexpected success, request-budget exhaustion, or unsafe uncertainty.
* It records enough evidence to explain the result without storing secrets.
* It handles CSRF login forms without unbounded retries.
* It handles redirects deterministically.
* It handles TLS errors, timeouts, and connection failures gracefully.
* It completes within the shared scan budget.
* It is idempotent against the local fixture.
* It has tests for confirmed, rejected, candidate, and safety-stop outcomes.
* It has negative tests proving the runner does not exceed attempt caps or continue after throttle signals.
* It does not hard-code hostname, framework, product, or fixture-specific behavior.
* It follows the Coding-agent rules in `../00-shared-schema.md`.

