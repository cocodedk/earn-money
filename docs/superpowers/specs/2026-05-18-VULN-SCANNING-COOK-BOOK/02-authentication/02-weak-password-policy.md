---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 2
spec: 2
slug: weak-password-policy
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 2.2 Weak password policy

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

Detect authentication flows that accept trivially weak passwords during registration, password change, or password reset completion. A runner cares because weak password policy allows easy account takeover when users choose common, short, or predictable passwords. This check must prove the behavior with controlled scanner-owned data, not by guessing user passwords.

## Inputs

The runner receives a shared `ScanTarget` and stores all observations as shared `Evidence`.

Required input:

* `target`: shared `ScanTarget`
* `base_url`: normalized from `target`
* `run_id`: current scan run identifier
* `scan_mode`: must allow authentication safety checks

Optional input:

* `credentials`: scanner-owned test account credentials

  * `username`
  * `email`
  * `current_password`
  * `restore_password`
* `registration_profile`: data used only for creating a scanner-owned canary account

  * `email_domain`
  * `username_prefix`
  * `display_name`
* `known_endpoints`: caller-supplied auth endpoints, if available

  * `register_url`
  * `login_url`
  * `change_password_url`
  * `reset_password_url`
* `policy_baseline`:

  * `min_length`, default `8`
  * `reject_common_passwords`, default `true`
  * `reject_username_as_password`, default `true`
  * `reject_all_numeric`, default `true`
* `limits`:

  * `max_candidate_passwords_per_endpoint`, default `3`
  * `max_mutating_requests`, default `4`
  * `timeout_ms`, default from shared HTTP settings
  * `follow_redirects`, default `true`
* `allow_registration_attempt`, default `false`
* `allow_password_change_attempt`, default `false`
* `allow_reset_completion_attempt`, default `false`
* `cleanup_created_accounts`, default `best_effort`

The runner must not require real user credentials. If no scanner-owned account or registration permission is provided, active detection is skipped and only passive evidence may be recorded as `candidate`.

## Detection logic

Detection is deterministic. Do not use AI.

### Endpoint discovery

Use only evidence from the target:

1. Crawl same-origin pages already allowed by the shared scanner scope.
2. Parse forms with password fields.
3. Parse OpenAPI or route metadata already discovered by earlier stubs.
4. Classify candidate flows by form fields, labels, submit text, paths, and HTTP method.

Flow classification hints:

| Flow             | Strong evidence                                                                                                                   |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Registration     | password field plus email or username field; action path contains `register`, `signup`, `create-account`, or equivalent body text |
| Login            | password field plus username/email field; action path or submit text indicates sign-in                                            |
| Password change  | `current_password` plus `new_password`, or authenticated page containing password update form                                     |
| Reset completion | token field or reset-token URL plus new password fields                                                                           |

Do not hard-code hostnames to expected behavior. Detect the flow from response evidence.

### Passive checks

Passive checks are not enough to confirm the finding.

Record passive `candidate` evidence when a discovered password form has one or more of:

* no `minlength` attribute
* `minlength` lower than the configured baseline
* no visible server-side policy text near the password field
* client-side-only policy checks
* JavaScript bundle or inline script showing a low minimum length
* policy text that allows short or common passwords

Passive checks produce `confidence: low` unless paired with active server acceptance.

### Active checks

Active checks may mutate target state and are opt-in.

Allowed active checks:

1. **Registration canary**

   * Only when `allow_registration_attempt=true`.
   * Generate a unique scanner-owned email and username.
   * Submit one weak password candidate at a time.
   * Stop after the first accepted weak password.
   * If registration succeeds, attempt a normal login roundtrip with the same weak password when a login endpoint is known.

2. **Password change on scanner-owned account**

   * Only when `allow_password_change_attempt=true`.
   * Require `credentials.current_password` and `credentials.restore_password`.
   * Attempt changing the scanner-owned account password to one weak candidate.
   * If accepted, try to restore the original or configured restore password.
   * If restore fails, mark cleanup as failed and require human review.

3. **Reset completion**

   * Only when `allow_reset_completion_attempt=true`.
   * Use only a reset token supplied by the test harness or fixture.
   * Do not request password reset emails for unknown users.
   * Do not enumerate users.

Default weak password candidates:

| Candidate class | Example                        | Positive signal                                          |
| --------------- | ------------------------------ | -------------------------------------------------------- |
| Too short       | `a`                            | accepted below `policy_baseline.min_length`              |
| Common word     | `password`                     | accepted when common-password rejection is required      |
| Numeric only    | `12345678`                     | accepted when numeric-only rejection is required         |
| Username reuse  | generated username as password | accepted when username-as-password rejection is required |

Candidate generation rules:

* Use at most `max_candidate_passwords_per_endpoint`.
* Do not use leaked password lists.
* Do not brute force.
* Do not retry many variants.
* Do not test against real user accounts.
* Do not continue after one confirmed weak acceptance for the same flow.

### Positive detection

A finding is confirmed when the server accepts a weak password in a controlled flow.

Accepted means one or more of:

* account creation response is a success status and body or redirect indicates successful registration
* login roundtrip succeeds with the weak password
* password change endpoint returns success and the weak password works for the scanner-owned account
* reset completion endpoint returns success and the weak password works for the scanner-owned account

Status-code-only evidence is not enough when the body clearly shows validation failure.

Validation failure patterns that must be treated as rejection:

* body contains password validation error text
* response returns field-level password errors
* redirect returns to the same form with password error
* JSON response contains `success: false`, `valid: false`, or equivalent error field
* HTTP `400`, `401`, `403`, or `422` with password policy error

### Confidence

Use these confidence rules:

* `high`: weak password accepted and verified through login or authenticated session continuity.
* `medium`: weak password accepted by a clear server success response, but login roundtrip was not possible.
* `low`: passive evidence only, ambiguous response, or policy appears weak but no controlled acceptance was proven.

### Rejection and stale handling

Create a `rejected` finding only when a previously suspected endpoint was retested and the server clearly rejects all configured weak candidates.

Mark a previous finding `stale` when:

* the endpoint no longer exists
* the flow is no longer reachable
* the shared target fingerprint changed enough that previous evidence cannot be tied to the current target

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them.

Define only stub-specific persistence types:

```ts
type WeakPasswordPolicySignature = {
  id: string;
  target_id: string;
  flow: "registration" | "password_change" | "reset_completion" | "unknown";
  endpoint_url: string;
  http_method: "GET" | "POST" | "PUT" | "PATCH";
  form_fingerprint: string;
  candidate_class:
    | "too_short"
    | "common_password"
    | "numeric_only"
    | "username_as_password"
    | "passive_policy_hint";
  accepted: boolean;
  verified_login: boolean;
  server_rejected: boolean;
  evidence_ids: string[];
  created_at: string;
};

type WeakPasswordPolicyFinding = {
  id: string;
  target_id: string;
  signature_id: string;
  status: "candidate" | "confirmed" | "rejected" | "stale";
  confidence: "low" | "medium" | "high";
  flow: "registration" | "password_change" | "reset_completion" | "unknown";
  endpoint_url: string;
  weak_password_class:
    | "too_short"
    | "common_password"
    | "numeric_only"
    | "username_as_password"
    | "passive_policy_hint";
  baseline_violation: string;
  evidence_ids: string[];
  cleanup_status:
    | "not_needed"
    | "completed"
    | "failed"
    | "not_attempted";
  human_review_required: boolean;
  summary: string;
  remediation: string;
  first_seen_at: string;
  last_seen_at: string;
};
```

Evidence records should include:

* request method and URL
* response status
* redirect chain, if any
* relevant response body snippet
* matched success or rejection markers
* form fingerprint
* weak password candidate class, not the literal password when avoidable
* cleanup result for created or modified accounts

Do not store plaintext passwords in findings. If a test password must be referenced for audit, store only its candidate class and a stable hash with the run salt.

Finding de-duplication key:

* `target_id`
* normalized endpoint URL
* flow
* candidate class
* form fingerprint

## Safety

This check is passive by default. Active checks are opt-in because registration, password change, and reset completion can mutate application state.

HTTP discipline:

* `GET` may be used for discovery.
* `POST`, `PUT`, and `PATCH` may be used only for controlled auth flows when the matching `allow_*` flag is true.
* `DELETE` must never be used.
* Authenticated requests must use only scanner-owned credentials.
* Password restore must be attempted after any successful password change.

Payload restrictions:

* Use only a short fixed candidate set.
* Do not use breached password corpora.
* Do not brute force accounts.
* Do not test passwords against real or third-party accounts.
* Do not perform username enumeration.
* Do not request reset links for arbitrary users.
* Do not bypass CAPTCHA, MFA, email verification, rate limits, or anti-abuse controls.
* Do not keep trying after the first confirmed weak-password acceptance for a flow.

PII handling:

* Use generated canary identities.
* Do not store email inbox contents.
* Do not persist plaintext passwords.
* Redact cookies, CSRF tokens, session IDs, reset tokens, and authorization headers from logs.
* Store only minimal response snippets needed to prove acceptance or rejection.

AI involvement: `None`.

Named deterministic gap:

* If the application requires email verification, CAPTCHA, MFA, invite approval, or out-of-band reset delivery, the runner must not bypass it. Record a low-confidence `candidate` only if passive evidence suggests weak policy, and set `human_review_required=true`.

## Pass/fail check

The implementation passes when all assertions below are true.

### Positive assertions

* The runner discovers password-bearing forms from same-origin evidence.
* The runner classifies registration, password change, and reset completion flows from response evidence.
* Passive weak-policy hints create only `candidate` findings with `confidence: low`.
* Active checks run only when the matching `allow_*` flag is true.
* A weak password accepted by the server creates a `confirmed` finding.
* A weak password accepted and verified by login creates `confidence: high`.
* A clear server success response without login verification creates `confidence: medium`.
* Server-side password rejection creates no confirmed finding.
* Findings reference shared `Evidence` IDs.
* Findings use only `low`, `medium`, or `high` confidence.
* Findings use only `candidate`, `confirmed`, `rejected`, or `stale` status.
* Password-change tests restore the scanner-owned account password when the weak change succeeds.
* Cleanup failure sets `cleanup_status: failed` and `human_review_required: true`.

### Negative assertions

* The runner must not use AI.
* The runner must not hard-code hostname, product name, or fixture name to expected behavior.
* The runner must not redefine shared `ScanTarget` or shared `Evidence`.
* The runner must not store plaintext passwords in findings.
* The runner must not use leaked password lists.
* The runner must not brute force.
* The runner must not test against real user accounts.
* The runner must not request password reset emails for arbitrary users.
* The runner must not bypass CAPTCHA, MFA, invite gates, or email verification.
* The runner must not use `DELETE`.
* The runner must not run mutating requests when active flags are false.
* The runner must not keep trying more weak passwords after one confirmed acceptance on the same flow.
* The runner must not treat status `200` alone as success when the body contains validation failure.
* The runner must not mark passive HTML constraints as confirmed server behavior.
* The runner must not leak cookies, CSRF tokens, session IDs, authorization headers, reset tokens, or credentials to logs.

## Test fixtures

Use `juice-shop` as the primary fixture if the container exposes user registration that accepts a weak password.

Expected fixture behavior:

* Registration endpoint is reachable from the public UI or API.
* Scanner can create a canary account with a weak password such as the configured common-password candidate.
* Scanner can verify login with the canary account.
* The created account is scanner-owned and uses a unique generated email.

Use `webgoat` as a secondary fixture only if the local lesson exposes a controlled password policy weakness without needing a real mailbox or external service.

Use a new fixture slug `weak-password-policy-lab` if existing fixtures are unstable. The fixture should expose:

* `GET /register` returning a registration form
* `POST /register` accepting `email`, `username`, and `password`
* `POST /login` allowing login for created accounts
* one intentionally weak mode that accepts `password`
* one strict mode that rejects `password`, `12345678`, username-as-password, and short passwords
* deterministic JSON or HTML responses for success and rejection

Fixture assertions:

* Weak mode produces one `confirmed` finding with `confidence: high`.
* Strict mode produces no confirmed finding.
* Passive-only mode produces at most one `candidate` finding with `confidence: low`.
* Password literals are not stored in the finding body.
* Evidence snippets are redacted.

## Acceptance criteria

The stub is acceptable when:

* It is idempotent across repeated scans against the same target and fixture.
* It completes within the shared per-target budget.
* It respects `max_candidate_passwords_per_endpoint` and `max_mutating_requests`.
* It handles TLS errors through the shared HTTP error path.
* It handles connection timeout, DNS failure, redirect loops, malformed HTML, malformed JSON, and missing CSRF fields without crashing.
* It uses shared HTTP client, scope, evidence, logging, and persistence patterns from `../00-shared-schema.md`.
* It detects CSRF fields from forms and replays them only for same-origin controlled submissions.
* It does not follow cross-origin form actions unless the shared scope allows them.
* It records enough evidence to reproduce the result without storing secrets.
* It produces stable de-duplication keys.
* It does not create flaky retries.
* It stops after one confirmed weak-password acceptance per flow.
* It cleans up or flags cleanup failure for any scanner-created or scanner-modified account.
* It has unit tests for passive detection, active registration, password change restore, rejection parsing, redaction, limits, and disabled active mode.
* It has fixture tests for weak mode and strict mode.
* It has no network calls outside the target scope.

