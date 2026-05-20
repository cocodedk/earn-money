---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 2
spec: 1
slug: username-enumeration
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 2.1 Username enumeration

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

Detect authentication flows that reveal whether a username, email address, or account identifier exists. The runner cares because different errors such as “user not found” versus “wrong password” let attackers build valid account lists before phishing, password spraying, or social engineering.

## Inputs

The runner receives a shared `ScanTarget` and writes shared `Evidence` records. This stub does not redefine either type.

Required inputs:

* `target`: shared `ScanTarget`.
* `base_url`: normalized target origin from `ScanTarget`.
* `discovered_auth_endpoints`: optional list from earlier crawling or route discovery.
* `known_valid_identifiers`: optional scoped identifiers provided by fixture config, user config, seeded test data, or authenticated scan setup.
* `scanner_config`: stub-specific knobs listed below.

Config knobs:

| Name                                            | Default | Purpose                                                                                 |
| ----------------------------------------------- | ------: | --------------------------------------------------------------------------------------- |
| `enabled`                                       |  `true` | Allows this stub to run.                                                                |
| `max_login_endpoints`                           |     `5` | Maximum auth endpoints tested per target.                                               |
| `max_submit_requests_per_endpoint`              |     `2` | Default one valid-control request and one invalid-control request.                      |
| `max_get_requests_per_endpoint`                 |     `2` | Fetch form and, if needed, refresh CSRF/session state.                                  |
| `request_timeout_ms`                            | `10000` | Per-request timeout.                                                                    |
| `follow_redirects`                              | `false` | Keep redirect behavior visible as evidence.                                             |
| `allow_common_login_path_probe`                 |  `true` | Allows bounded GET probing for common login paths when no auth endpoint was discovered. |
| `allow_password_reset_probe`                    | `false` | Disabled by default because reset flows may send email or create audit events.          |
| `allow_timing_signal`                           | `false` | Timing is not used for confirmation in the first implementation.                        |
| `known_valid_identifier_required_for_confirmed` |  `true` | Prevents confirmed findings based only on guessed usernames.                            |
| `redact_identifiers_in_logs`                    |  `true` | Raw usernames and emails must not be logged.                                            |

Optional candidate paths for bounded GET discovery only, when the crawler has not supplied auth endpoints:

* `/login`
* `/signin`
* `/sign-in`
* `/account/login`
* `/user/login`
* `/auth/login`
* `/admin/login`

These paths are hints, not technology assumptions. The runner must decide from response evidence whether a path is an auth form or API endpoint.

Identifier handling:

* The invalid control identifier must be generated per scan.
* For email fields, use an address under `example.invalid`, such as `scanner-<nonce>@example.invalid`.
* For username fields, use a non-human synthetic value such as `scanner_invalid_<nonce>`.
* Do not scrape public names, employee emails, comments, profile pages, or leaked data to build username candidates.
* Do not use customer-provided real user lists unless the scan configuration explicitly marks them as in-scope test identifiers.
* Use one generated bogus password value for both valid and invalid probes so request shape stays comparable.

## Detection logic

Detection is deterministic. The runner compares controlled login or reset attempts against the same endpoint and records differences in status, redirect behavior, structured error fields, and normalized body text.

### 1. Find authentication candidates

Use these sources, in order:

1. `discovered_auth_endpoints` from crawler or prior phases.
2. HTML forms discovered on candidate pages.
3. JSON endpoints discovered by API route crawling.
4. Bounded GET probes to common login paths, only when enabled.

A page is an auth candidate when response evidence shows one or more of:

* An HTML form with a password field.
* An HTML form with an input named like `username`, `email`, `login`, `identifier`, `user`, or `account`.
* A JSON or API endpoint with route or response evidence suggesting login.
* A page title, label, button, or form action that indicates sign-in behavior.

Do not assume technology from hostname, path alone, server header alone, or favicon alone.

### 2. Build comparable requests

For each endpoint:

1. Fetch the form or endpoint metadata with `GET`.
2. Extract method, action URL, input names, CSRF fields, hidden fields, and content type.
3. Build one invalid-control request.
4. Build one valid-control request only when a safe known valid identifier is available.
5. Use the same bogus password for both requests.
6. Preserve request shape:

   * Same method.
   * Same parameter names.
   * Same content type.
   * Same header set, except dynamic cookies and CSRF values.
   * Same redirect policy.
   * Same user agent.
7. Re-fetch the form before each submit when the target uses CSRF tokens or per-request hidden fields.

Do not submit guessed “common” usernames such as `admin`, `test`, `user`, or `administrator` unless they are provided by the fixture or scan config as scoped valid identifiers.

### 3. Submit low-volume probes

Login probes may submit a failed login request. This is active behavior, but it must stay bounded.

Default request pattern per endpoint:

| Request         | Identifier                             | Password                      | Purpose                                 |
| --------------- | -------------------------------------- | ----------------------------- | --------------------------------------- |
| Invalid control | Generated synthetic invalid identifier | Generated bogus password      | Baseline for nonexistent account.       |
| Valid control   | Scoped known valid identifier          | Same generated bogus password | Compare against known existing account. |

Password reset probes are disabled by default. If enabled, they must follow the same valid-versus-invalid comparison pattern, but must not follow reset links, OTP flows, magic links, email verification links, or MFA flows.

### 4. Normalize responses before comparison

Normalize response evidence before diffing.

Remove or replace:

* CSRF values.
* Request IDs.
* Trace IDs.
* Session IDs.
* Timestamps.
* Nonces.
* UUIDs.
* Random-looking tokens.
* Dynamic numeric counters where safe.
* Set-Cookie values.
* HTML whitespace differences.
* Known framework noise already handled by shared normalization utilities.

Keep:

* HTTP status.
* Redirect target path and query-key names, with sensitive values redacted.
* JSON error codes and field names.
* Form-level and field-level error messages.
* Response title.
* Stable body text snippets around the error area.
* Content type.
* Relevant headers that affect control flow, such as `Location`.

### 5. Compare deterministic signals

Create a signature when one or more controlled differences are present.

Strong signals:

* Invalid identifier returns text like “user not found”, “unknown user”, “no account exists”, or “email is not registered”.
* Valid identifier with the same bogus password returns text like “incorrect password”, “invalid password”, “MFA required”, “check your authenticator”, or “account locked”.
* JSON error codes differ, such as `USER_NOT_FOUND` versus `BAD_PASSWORD`.
* HTTP statuses differ in a stable way, such as `404` for invalid account and `401` for valid account.
* Redirect behavior differs, such as invalid staying on `/login` while valid moves to `/mfa` or `/verify`.
* Field-level errors differ, such as `email: not found` versus `password: incorrect`.

Weak signals:

* Only generic body length differs.
* Only response timing differs.
* Only header ordering differs.
* Only dynamic tokens differ after normalization.
* Only wording suggests no account exists, with no known-valid control.

Timing must not be used to confirm this finding in the first implementation. If timing is collected for diagnostics, store it as supporting metadata only and keep confidence `low`.

### 6. Set confidence and status

Use these rules:

| Condition                                                                                                                          | Status      | Confidence |
| ---------------------------------------------------------------------------------------------------------------------------------- | ----------- | ---------- |
| Known valid control and synthetic invalid control produce a clear semantic difference in errors, JSON codes, status, or redirects. | `confirmed` | `high`     |
| Known valid control and synthetic invalid control differ, but only one stable signal is present from a single request pair.        | `confirmed` | `medium`   |
| Invalid-only probe returns explicit “user not found” style wording, but no known valid control was available.                      | `candidate` | `low`      |
| Responses are generic after normalization and no stable differentiator exists.                                                     | `rejected`  | `high`     |
| Probe was stopped because of CAPTCHA, lockout, rate limit, WAF, TLS failure, or unsafe side effect risk.                           | `stale`     | `low`      |

A finding must not be `confirmed` without a known valid control unless a fixture-specific deterministic oracle is explicitly configured.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`.

Persist raw HTTP evidence using the shared evidence model. Store only redacted snippets in the stub-specific finding. Do not store raw passwords. Do not store raw real usernames or real email addresses outside the secure evidence layer.

Define only these stub-specific types:

```ts
export interface UsernameEnumerationSignature {
  signature_id: string;
  endpoint_url: string;
  method: "GET" | "POST";
  channel: "login" | "password_reset" | "api_login";
  identifier_parameter: string;
  password_parameter?: string;
  content_type: string;

  valid_identifier_source:
    | "fixture"
    | "scan_config"
    | "provided_credentials"
    | "authenticated_context"
    | "none";

  valid_identifier_fingerprint?: string;
  invalid_identifier_fingerprint: string;

  differentiators: Array<{
    kind:
      | "status_code"
      | "redirect_location"
      | "json_error_code"
      | "field_error"
      | "body_text"
      | "title_text"
      | "body_length";
    invalid_value_redacted: string;
    valid_value_redacted?: string;
    explanation: string;
  }>;

  normalized_invalid_response_hash: string;
  normalized_valid_response_hash?: string;

  evidence_ids: string[];
  confidence: "low" | "medium" | "high";
  status: "candidate" | "confirmed" | "rejected" | "stale";
}

export interface UsernameEnumerationFinding {
  finding_id: string;
  target: ScanTarget;
  signature: UsernameEnumerationSignature;

  title: string;
  summary: string;
  affected_endpoint: string;
  affected_parameter: string;
  enumeration_channel: "login" | "password_reset" | "api_login";

  evidence: Evidence[];
  evidence_ids: string[];

  severity_hint: "info" | "low" | "medium";
  confidence: "low" | "medium" | "high";
  status: "candidate" | "confirmed" | "rejected" | "stale";

  remediation: {
    summary: string;
    steps: string[];
  };

  created_at: string;
  updated_at: string;
}
```

Evidence records should include, where available:

* Auth form snapshot.
* Invalid-control request metadata.
* Invalid-control response metadata.
* Valid-control request metadata, if used.
* Valid-control response metadata, if used.
* Normalized diff summary.
* Safety abort reason, if the runner stops early.

Recommended remediation text:

* Use the same generic error message for nonexistent users and wrong passwords.
* Keep status code, redirect behavior, response shape, and JSON error schema consistent.
* Rate-limit authentication attempts by account and source.
* Add monitoring for enumeration patterns.
* Avoid saying whether password reset emails were sent for a specific address.
* Make MFA and lockout responses indistinguishable from generic login failure where practical.

## Safety

This stub is not fully read-only because login and reset forms may update failed-login counters, audit logs, rate limits, or notification state. Keep probes low-volume and controlled.

Rules:

* Use `GET` for discovery.
* Use `POST` only for a form or API endpoint that response evidence identifies as authentication-related.
* Do not perform password spraying.
* Do not brute-force usernames.
* Do not try common usernames by default.
* Do not submit more than one bogus password per identifier per endpoint unless fixture mode explicitly allows a repeat.
* Do not reuse real passwords.
* Do not attempt successful login.
* Do not follow MFA, OTP, reset-link, magic-link, or email-verification flows.
* Do not bypass CAPTCHA, rate limits, WAF, lockout, or account protection controls.
* Stop testing an endpoint when the response indicates CAPTCHA, lockout, throttling, abuse detection, or account protection.
* Stop testing on `429`, clear WAF block pages, or lockout wording.
* Do not test password reset endpoints unless `allow_password_reset_probe=true`.
* Do not submit real user email addresses to password reset flows unless explicitly scoped.
* Do not send reset probes to addresses that could reach real people.
* Prefer fixture domains such as `example.invalid` for synthetic controls.
* Redact identifiers in logs and findings.
* Store identifier fingerprints with a project secret or shared hashing helper when available.
* Never log passwords, cookies, CSRF tokens, session IDs, or authorization headers.
* AI involvement: `None`.

No deterministic AI gap is defined for this stub. The runner has enough deterministic evidence from controlled request pairs and response comparison.

## Pass/fail check

A coding agent implementation passes when these assertions hold.

Positive assertions:

* It accepts a shared `ScanTarget` and writes shared `Evidence`.
* It does not redefine shared `ScanTarget` or `Evidence`.
* It detects an HTML login form from response evidence, not from hostname assumptions.
* It extracts username/email and password parameter names from the form.
* It refreshes CSRF or hidden fields before submit when required.
* It sends the same bogus password for valid and invalid controls.
* It uses a generated synthetic invalid identifier.
* It uses a known valid identifier only when supplied by fixture, scan config, provided credentials, or authenticated scan context.
* It records both valid-control and invalid-control evidence when both are used.
* It normalizes dynamic tokens before comparing bodies.
* It flags different messages such as “unknown user” versus “incorrect password”.
* It flags different JSON error codes such as `USER_NOT_FOUND` versus `BAD_PASSWORD`.
* It can create a `confirmed` finding with `medium` or `high` confidence when a known valid control and invalid control differ.
* It can create a `candidate` finding with `low` confidence when only invalid-side explicit enumeration wording exists.
* It can create a `rejected` finding when normalized responses are generic and equivalent.
* It creates `stale` status when testing is stopped by rate limits, CAPTCHA, lockout, TLS failure, or unsafe side-effect risk.
* It stores evidence IDs on the signature and finding.
* It produces remediation steps that recommend generic errors and consistent response behavior.

Negative assertions:

* It must not mark a finding `confirmed` from a guessed username alone.
* It must not submit a list of common usernames.
* It must not scrape usernames or emails from the target and test them by default.
* It must not use response timing as the only confirmation signal.
* It must not hard-code hostname-to-technology assumptions.
* It must not attempt a successful login.
* It must not follow MFA, OTP, password reset, magic-link, or email verification flows.
* It must not bypass CAPTCHA, lockout, WAF, or throttling controls.
* It must not keep retrying after `429`, lockout wording, CAPTCHA, or abuse detection.
* It must not store raw passwords.
* It must not log cookies, CSRF tokens, authorization headers, or session IDs.
* It must not store raw real usernames or emails in the finding body.
* It must not call an LLM.
* It must not send password reset probes unless the config explicitly enables them.
* It must not create a `high` confidence finding from body length alone.
* It must not fail the scan when an auth endpoint is missing; it should return no finding or `rejected` evidence according to project style.

## Test fixtures

Use a new fixture slug: `username-enumeration`.

The fixture should expose deterministic vulnerable and safe variants.

Required fixture routes:

| Route                        | Behavior                                                                                                                  | Expected result                                     |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| `/login-vulnerable`          | HTML form. Seeded valid identifier returns “Incorrect password”. Synthetic invalid identifier returns “No account found”. | `confirmed`, `high`                                 |
| `/login-generic`             | HTML form. Both valid and invalid identifiers return “Invalid username or password”.                                      | `rejected`, `high`                                  |
| `/api/login-vulnerable`      | JSON API. Valid identifier returns `BAD_PASSWORD`; invalid identifier returns `USER_NOT_FOUND`.                           | `confirmed`, `high`                                 |
| `/api/login-generic`         | JSON API. Both controls return the same generic error code.                                                               | `rejected`, `high`                                  |
| `/login-csrf`                | HTML form with per-request CSRF token.                                                                                    | Runner refreshes token and still detects correctly. |
| `/login-lockout`             | Returns lockout or CAPTCHA after first failed attempt.                                                                    | `stale`, `low`; runner stops.                       |
| `/password-reset-vulnerable` | Disabled unless `allow_password_reset_probe=true`. Valid and invalid identifiers produce different generic-safe text.     | Only tested when enabled.                           |

Seeded fixture identifiers:

* Valid: `alice@example.invalid`
* Invalid: generated by runner under `example.invalid`
* Bogus password: generated by runner, never equal to the fixture password

Container feature requirement:

* The fixture must reset failed-login counters between tests.
* The fixture must expose stable response bodies.
* The fixture must not send real email.
* Password reset behavior must use an in-memory sink, not an external mail service.
* Tests must not depend on timing thresholds.

Optional compatibility fixtures:

* `dvwa` may be used only if the local fixture adapter provides a scoped valid identifier and resettable state.
* `juice-shop` and `webgoat` may be used for exploratory adapter tests, but they must not be the only acceptance fixture unless their behavior is stable in CI.

## Acceptance criteria

The implementation is acceptable when:

* The runner is idempotent against the test fixture.
* The runner completes within the configured request budget.
* The default scan uses at most two submit requests per endpoint.
* The runner handles TLS errors, connection errors, invalid HTML, invalid JSON, redirects, and missing forms without crashing.
* The runner does not perform username brute forcing.
* The runner does not perform password spraying.
* The runner does not attempt successful authentication.
* The runner does not submit reset forms unless explicitly enabled.
* The runner stops on CAPTCHA, lockout, WAF block, abuse detection, or `429`.
* The runner records enough evidence to reproduce the comparison without storing raw secrets in logs.
* The runner uses deterministic normalization before diffing responses.
* The runner produces stable results across repeated fixture runs.
* The runner reports `confirmed`, `candidate`, `rejected`, and `stale` statuses correctly.
* The runner maps confidence only to `low`, `medium`, or `high`.
* The runner uses shared persistence conventions from `../00-shared-schema.md`.
* The runner defines only `UsernameEnumerationSignature` and `UsernameEnumerationFinding` as stub-specific types.
* The runner has unit tests for form extraction, CSRF refresh, request shaping, normalization, diff classification, redaction, and safety aborts.
* The runner has fixture tests for vulnerable HTML login, safe HTML login, vulnerable JSON login, safe JSON login, CSRF login, lockout behavior, and disabled password reset probing.
* The runner has no real network dependency outside the target fixture.
* AI is not called.

