---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 2
spec: 3
slug: missing-lockout
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 2.3 Missing lockout

> Phase 2 — Authentication · Category: Weak login behavior

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

Detect login flows that allow repeated failed authentication attempts for the same account without a lockout, cooldown, rate limit, CAPTCHA challenge, or other blocking control. A runner cares because missing lockout makes password guessing more practical, but this check must stay tightly bounded and must only use a scanner-owned test account.

## Inputs

The runner receives the shared `ScanTarget` plus optional authentication test settings.

Required:

* `ScanTarget` from `../00-shared-schema.md`.

Optional config:

| Field                        |           Type |       Default | Notes                                                           |                                                                                       |
| ---------------------------- | -------------: | ------------: | --------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `login_url`                  |        `string |         null` | `null`                                                          | Explicit login endpoint. If absent, the runner may use passive discovery.             |
| `test_username`              |        `string |         null` | `null`                                                          | Scanner-owned account only. Must not be a real user account.                          |
| `test_password`              |        `string |         null` | `null`                                                          | Correct password for the scanner-owned account. Needed for post-failure verification. |
| `wrong_password`             |       `string` |     generated | Synthetic wrong password. Must not come from leaked lists.      |                                                                                       |
| `max_failed_attempts`        |          `int` |           `5` | Hard cap. Must not exceed the global safe maximum.              |                                                                                       |
| `global_max_failed_attempts` |          `int` |           `5` | Absolute implementation guardrail.                              |                                                                                       |
| `request_timeout_ms`         |          `int` |       `10000` | Per HTTP request timeout.                                       |                                                                                       |
| `delay_between_attempts_ms`  |          `int` |         `750` | Delay between failed attempts.                                  |                                                                                       |
| `max_login_candidates`       |          `int` |           `3` | Passive discovery cap.                                          |                                                                                       |
| `success_indicator`          |        `string |         null` | `null`                                                          | Optional deterministic marker for successful login.                                   |
| `failure_indicator`          |        `string |         null` | `null`                                                          | Optional deterministic marker for failed login.                                       |
| `lockout_indicators`         | `list[string]` | built-in list | Extra strings or selectors that indicate blocking.              |                                                                                       |
| `dry_run`                    |         `bool` |       `false` | If true, discover and classify only. Do not submit credentials. |                                                                                       |

Input validation:

* If `test_username` or `test_password` is missing, the runner must not submit login attempts.
* If `max_failed_attempts > global_max_failed_attempts`, clamp to `global_max_failed_attempts` and record that in evidence metadata.
* If the configured username looks like a production or personal account and the target is not an approved fixture, reject active testing unless the caller explicitly marks the account as scanner-owned.
* Never accept password dictionaries, leaked credential files, or username lists as input for this stub.

## Detection logic

Detection is deterministic and has two modes.

### Mode A: passive candidate detection

Use this mode when credentials are absent or `dry_run=true`.

1. Fetch the target root and same-origin links within the shared crawl budget.
2. Identify login candidates by response evidence:

   * HTML form with `input[type=password]`
   * submit button or form text containing `login`, `log in`, `sign in`, `authenticate`
   * endpoint path containing `/login`, `/signin`, `/auth`, `/session`
   * JSON API route names found in public JavaScript that contain `login`, `signin`, or `session`
3. Record evidence for each candidate:

   * URL
   * method
   * status code
   * content type
   * form field names
   * CSRF field presence
   * visible lockout or throttling messages, if present
4. Do not infer missing lockout only because a login form exists.
5. Return:

   * `candidate` with `confidence=low` if a login flow exists but active testing was not allowed.
   * `rejected` if no login flow is found inside the crawl budget.

Passive mode may detect lockout-related UI or messages, but it must not confirm absence of lockout.

### Mode B: bounded scanner-owned account probe

Use this mode only when a scanner-owned test account and correct password are configured.

1. Resolve the login endpoint:

   * Prefer `login_url`.
   * Otherwise use the best passive candidate.
   * Do not test more than `max_login_candidates`.
2. Establish a baseline:

   * Submit one known-good login using `test_username` and `test_password`.
   * Confirm success using status, redirect, session cookie change, `success_indicator`, or another deterministic project-approved verifier.
   * If success cannot be verified, stop and return `stale` or `rejected` with evidence explaining why the probe could not run.
3. Clear session state:

   * Use a fresh cookie jar for each failed attempt unless the existing project login helper requires a persistent jar.
   * Do not reuse authenticated cookies for failed attempts.
4. Submit bounded failed attempts:

   * Same `test_username`.
   * Same synthetic `wrong_password`.
   * At most `max_failed_attempts`.
   * Wait `delay_between_attempts_ms` between attempts.
5. After each failed attempt, inspect deterministic evidence:

   * HTTP status code
   * redirect target
   * response body text or JSON error code
   * headers indicating rate limit or cooldown
   * lockout/captcha/challenge messages
   * account disabled or temporarily blocked messages
6. Stop early if any lockout, cooldown, rate limit, CAPTCHA, MFA challenge, or equivalent blocking control appears.
7. After the final failed attempt, submit one known-good login with the scanner-owned account:

   * If known-good login still succeeds and no blocking control appeared, create a finding.
   * If known-good login is blocked or delayed, reject the missing-lockout finding and record the observed protection.
   * If the result is ambiguous, return `candidate` with `confidence=low` and `requires_manual_review=true`.

Built-in lockout indicators include case-insensitive matches for:

```text
account locked
account temporarily locked
too many attempts
too many failed attempts
try again later
temporarily disabled
temporarily blocked
rate limit
slow down
captcha
verification required
additional verification
maximum login attempts
```

### Classification

Confirmed finding:

* A scanner-owned account successfully logs in before the probe.
* The runner submits the configured number of failed attempts.
* No deterministic lockout, cooldown, CAPTCHA, or rate-limit signal is observed.
* The same account can still log in successfully immediately after the failed attempts.

Candidate finding:

* Login flow exists, but active testing is not allowed.
* Active probe ran but the result is ambiguous.
* The runner saw no blocking signal, but could not verify post-failure successful login.

Rejected finding:

* No login flow is found inside budget.
* The endpoint blocks, delays, challenges, or locks the account during the bounded probe.
* Baseline login cannot be verified.
* The configured account is not scanner-owned.

Stale finding:

* Previous evidence no longer matches the current endpoint.
* Login endpoint disappeared.
* Response shape changed enough that the stored signature no longer applies.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Define only these stub-specific types:

```python
from typing import Literal, TypedDict


Confidence = Literal["low", "medium", "high"]
FindingStatus = Literal["candidate", "confirmed", "rejected", "stale"]


class MissingLockoutSignature(TypedDict):
    login_url: str
    method: Literal["POST", "PUT"]
    username_field: str
    password_field: str
    csrf_field: str | None
    success_signal: str | None
    failure_signal: str | None
    failed_attempts_sent: int
    lockout_signal_seen: bool
    post_failure_login_succeeded: bool | None
    response_status_sequence: list[int]
    response_hash_sequence: list[str]


class MissingLockoutFinding(TypedDict):
    target: "ScanTarget"
    status: FindingStatus
    confidence: Confidence
    signature: MissingLockoutSignature
    evidence: list["Evidence"]
    title: str
    summary: str
    risk: str
    remediation: str
    scanner_owned_account_used: bool
    requires_manual_review: bool
```

Persistence rules:

* Store one finding per tested login flow.
* Link every conclusion to evidence IDs.
* Store response hashes and short excerpts, not full credential-bearing request bodies.
* Do not store `test_password`, `wrong_password`, session cookies, CSRF token values, access tokens, or full submitted form bodies.
* Store field names and high-level request metadata only.
* If the finding is `confirmed`, include both baseline success evidence and post-failure success evidence.
* If rejected because protection was observed, store the protection signal as evidence.

## Safety

This stub is not fully read-only. Active mode mutates authentication state by creating failed login attempts on a scanner-owned test account. Keep it disabled unless safe credentials are provided.

Rules:

* Do not use leaked password lists.
* Do not brute force.
* Do not retry many variants.
* Do not test against real user accounts.
* Use exactly one scanner-owned username per run.
* Use one synthetic wrong password, not a list.
* Keep `max_failed_attempts` low. Default and hard maximum: `5`.
* Stop on the first lockout, cooldown, rate-limit, CAPTCHA, MFA, or challenge signal.
* Never continue after the account appears locked.
* Never try to bypass lockout, CAPTCHA, MFA, WAF, IP throttling, or rate limits.
* Never rotate IP addresses, user agents, usernames, passwords, cookies, or headers to avoid controls.
* Never submit credentials to cross-origin forms.
* Never submit to a login form unless the endpoint is same-origin or explicitly in scope.
* Never include production usernames in test fixtures.
* Never log passwords, cookies, authorization headers, CSRF token values, or full request bodies.
* Treat usernames as sensitive and store only the configured scanner-owned username or a redacted form where project policy requires it.

HTTP method discipline:

* Passive mode may use `GET` and `HEAD`.
* Active mode may use only the form or API method detected from evidence, usually `POST`.
* Do not use destructive methods.
* Do not fuzz methods.

Payload restrictions:

* Only submit the detected username, password, CSRF, and required static form fields.
* Do not add unexpected parameters.
* Do not inject payloads into username or password fields.
* Do not attempt SQL injection, XSS, command injection, or credential stuffing as part of this stub.

PII handling:

* Scanner-owned test usernames are allowed.
* Personal, employee, customer, or harvested usernames are not allowed.
* If a response includes personal data, store a minimized excerpt and mark the evidence as sensitive.

AI involvement:

* `None`.
* There is no deterministic gap that requires AI.
* If future work adds AI to explain the finding, it must consume only persisted evidence summaries and must not influence status, confidence, or active request decisions.

## Pass/fail check

A coding agent implementing this spec must satisfy these assertions.

### Positive assertions

* Given no credentials, the runner performs passive detection only.
* Given no credentials and a detected login form, the runner may create at most a `candidate` finding with `confidence=low`.
* Given a scanner-owned test account, the runner verifies baseline login before failed attempts.
* Given `max_failed_attempts=5`, the runner sends no more than five failed login submissions.
* Given a lockout message after attempt 3, the runner stops immediately and rejects the missing-lockout finding.
* Given a rate-limit status such as `429`, the runner stops immediately and rejects the missing-lockout finding.
* Given a CAPTCHA or additional verification challenge, the runner stops immediately and rejects the missing-lockout finding.
* Given five failed attempts, no blocking signal, and successful known-good login afterward, the runner creates a `confirmed` finding.
* Given ambiguous post-failure login verification, the runner creates a `candidate` finding with `confidence=low` and `requires_manual_review=true`.
* Given changed response signatures for a previously stored finding, the runner marks the old finding `stale`.

### Negative assertions

* The runner must not use leaked password lists.
* The runner must not test more than one username for this stub.
* The runner must not test more than one wrong password for this stub.
* The runner must not exceed `global_max_failed_attempts`.
* The runner must not test real user accounts.
* The runner must not continue after a lockout, cooldown, rate-limit, CAPTCHA, MFA, or challenge signal.
* The runner must not bypass or attempt to bypass any blocking control.
* The runner must not rotate source IP, cookies, headers, user agents, usernames, or passwords to avoid controls.
* The runner must not infer a confirmed missing lockout from passive evidence alone.
* The runner must not hard-code hostname, fixture name, framework, or expected technology.
* The runner must not log passwords, cookies, bearer tokens, CSRF token values, or full request bodies.
* The runner must not submit credentials to out-of-scope or cross-origin endpoints.
* The runner must not call an LLM for detection or classification.

### Example deterministic decision table

| Baseline login | Failed attempts | Blocking signal | Post-failure good login | Status      | Confidence |
| -------------- | --------------: | --------------- | ----------------------- | ----------- | ---------- |
| verified       |               5 | none            | succeeds                | `confirmed` | `medium`   |
| verified       |               3 | lockout         | not attempted           | `rejected`  | `high`     |
| verified       |               2 | `429`           | not attempted           | `rejected`  | `high`     |
| verified       |               5 | none            | unknown                 | `candidate` | `low`      |
| not verified   |               0 | n/a             | n/a                     | `rejected`  | `low`      |
| not attempted  |               0 | n/a             | n/a                     | `candidate` | `low`      |

## Test fixtures

Use fixtures that expose a controlled login flow and a scanner-owned account.

Preferred fixture: `webgoat`

* Feature: authentication lesson or custom fixture route with configurable lockout behavior.
* Required accounts:

  * `scanner-lockout-test@example.test`
* Required variants:

  * lockout disabled
  * lockout after 3 failed attempts
  * rate limit after 2 failed attempts
  * CAPTCHA/challenge simulated after failed attempts

Secondary fixture: `juice-shop`

* Use only if a scanner-owned test user can be created/reset deterministically before each test.
* Do not use real built-in user accounts unless the fixture explicitly documents them as test-only and resettable.

If neither fixture gives stable lockout behavior, add a new fixture slug:

* `auth-lockout-lab`

Required fixture routes:

| Route                       | Behavior                                                                |
| --------------------------- | ----------------------------------------------------------------------- |
| `/login/no-lockout`         | Accepts scanner-owned account. Never locks after failed attempts.       |
| `/login/lockout-after-3`    | Locks scanner-owned account after 3 failed attempts.                    |
| `/login/rate-limit-after-2` | Returns deterministic `429` after 2 failed attempts.                    |
| `/login/captcha-after-2`    | Returns deterministic CAPTCHA/challenge marker after 2 failed attempts. |
| `/login/ambiguous`          | Returns responses that do not allow post-failure success verification.  |

Fixture requirements:

* Reset account state before every test.
* Use only fake usernames and passwords.
* Never require internet access.
* Never call external identity providers.
* Emit deterministic response bodies and status codes.
* Include CSRF-token and no-CSRF variants if the shared login helper supports both.
* Keep account state isolated per test case.

## Acceptance criteria

* The runner is idempotent against resettable fixtures.
* The active probe only runs with a scanner-owned test account.
* Passive mode never submits credentials.
* Active mode performs a baseline success check before failed attempts.
* Active mode performs a post-failure success check only when no blocking control was observed.
* The runner completes within the shared per-target budget.
* The runner respects request timeout, crawl budget, candidate cap, and failed-attempt cap.
* The runner handles TLS errors according to shared transport policy and records a clean rejected/stale result instead of crashing.
* The runner handles network timeout, redirect loop, CSRF mismatch, changed form fields, and unexpected content type without unsafe retries.
* The runner uses deterministic evidence only.
* The runner emits stable evidence IDs.
* The runner persists minimized evidence and does not store secrets.
* The runner does not hard-code technology expectations by hostname or fixture name.
* The runner has unit tests for passive mode, active confirmed mode, lockout rejection, rate-limit rejection, CAPTCHA rejection, missing credentials, unsafe username rejection, cap enforcement, stale signature handling, and secret redaction.
* The runner has integration tests against the selected fixture or `auth-lockout-lab`.
* The runner does not call real external services.
* The runner does not call an LLM.
* The implementation follows the shared Coding-agent rules in `../00-shared-schema.md`.

