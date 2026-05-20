---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 1
spec: 13
slug: security-txt
status: done        # pending | in-progress | blocked | done
fixture: juice-shop # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 1.13 Security.txt

> Phase 1 — Information gathering · Category: Public metadata

## Purpose

Detect whether the target publishes a valid `security.txt` file, where it publishes it, and whether the file gives usable vulnerability disclosure contact metadata. A runner uses this as passive public metadata: it helps identify reporting channels, disclosure policy links, expiry state, and malformed or missing security contact data without interacting with the application beyond simple HTTP GET requests.

## Inputs

The runner receives:

* `ScanTarget` from `../00-shared-schema.md`.
* Optional HTTP client settings from the scan profile:

  * `timeout_seconds`, default `5`
  * `max_redirects`, default `3`
  * `max_body_bytes`, default `65536`
  * `user_agent`
  * `verify_tls`, default `true`
  * `prefer_https`, default `true`
  * `check_legacy_path`, default `true`
* Optional credential context from the scan session.

Credentials must not be used by this check. `security.txt` is public metadata. If the shared runner passes cookies, bearer tokens, session headers, or client certificates by default, this check must explicitly suppress them.

The check builds candidate URLs from `ScanTarget.base_url`:

1. `/.well-known/security.txt`
2. `/security.txt`, only as a legacy fallback or comparison path when `check_legacy_path=true`

The scanner must use the target host from `ScanTarget`. It must not hard-code hostnames, fixture names, or expected file contents.

## Detection logic

### Request discipline

Use deterministic HTTP only.

* Method: `GET`
* Headers:

  * `Accept: text/plain, */*;q=0.1`
  * configured scanner `User-Agent`
* Do not send:

  * cookies
  * bearer tokens
  * basic auth
  * custom user headers from earlier authenticated checks
  * request body

Fetch order:

1. Fetch `/.well-known/security.txt`.
2. If it returns a parseable `200`, use it as the primary file.
3. If it is absent or unusable, fetch `/security.txt` when `check_legacy_path=true`.
4. If both exist, prefer `/.well-known/security.txt` but record whether the legacy file differs.

A response is considered present when:

* final status is `200`
* body has at least one non-empty line after trimming whitespace
* body size is within `max_body_bytes`
* response is not a binary-looking payload

A response is considered absent when:

* status is `404` or `410`
* status is `204`
* body is empty after trimming

A response is considered blocked when:

* status is `401` or `403`

A response is considered inconclusive when:

* timeout occurs
* DNS/TLS/network error occurs
* redirect limit is exceeded
* body is larger than `max_body_bytes`
* body cannot be decoded as UTF-8 or mostly text

### Redirect handling

Follow redirects up to `max_redirects`.

Allowed redirects:

* same host
* same scheme or HTTP to HTTPS
* same port unless the target base URL includes a non-default port

Disallowed redirects:

* redirect to a different registrable domain
* redirect to an unrelated host
* redirect to a non-HTTP scheme
* redirect loop
* redirect chain longer than `max_redirects`

When a redirect is disallowed, stop following it and create evidence for the redirect response. Do not fetch the external target.

### Parsing

Parse only response bodies from candidate `security.txt` paths that pass the presence checks.

Parsing rules:

* Decode as UTF-8.
* Normalize line endings.
* Ignore blank lines.
* Ignore comment lines beginning with `#`.
* Parse field lines as `Name: value`.
* Field names are case-insensitive for recognition.
* Preserve original field name casing in evidence metadata.
* Trim leading and trailing whitespace around values.
* Keep repeated fields as arrays.
* Store unknown fields as `unknown_fields`; do not fail only because an unknown field exists.

Recognized fields:

* `Contact`
* `Expires`
* `Encryption`
* `Acknowledgments`
* `Preferred-Languages`
* `Canonical`
* `Policy`
* `Hiring`
* `CSAF`

Validation rules:

* `Contact`

  * At least one `Contact` field is required for a useful file.
  * Value must be a URI-like string.
  * Accepted schemes for this check: `mailto`, `https`, `http`, `tel`.
  * `http` contact URLs are allowed but produce a warning.
  * Do not call, email, open, or verify the contact target.
* `Expires`

  * Parse as RFC3339/ISO-8601 timestamp.
  * If missing, create a warning.
  * If present and older than scan time, create an expired finding.
  * If malformed, create a malformed-date finding.
* `Canonical`

  * If present, parse as absolute HTTP(S) URL.
  * If no `Canonical` value matches the final fetched URL, create a canonical mismatch finding.
  * If the file is served from `/security.txt` and `Canonical` points to `/.well-known/security.txt`, record this as legacy placement rather than immediate failure.
* URL-valued fields

  * For `Policy`, `Encryption`, `Acknowledgments`, `Hiring`, and `CSAF`, validate URI shape only.
  * Do not fetch linked resources.
* `Preferred-Languages`

  * Parse as comma-separated language tags.
  * Invalid tags produce warnings, not hard failure.

### Finding rules

Create findings from deterministic evidence:

* `missing_security_txt`

  * Neither canonical nor legacy path has a present file.
  * Confidence: `high` if both paths were fetched and returned absent statuses.
  * Confidence: `medium` if one path was inconclusive.
* `blocked_security_txt`

  * Candidate path returns `401` or `403`.
  * Confidence: `high`.
* `malformed_security_txt`

  * Present file exists but has malformed field lines, malformed dates, binary-looking text, or no parseable fields.
  * Confidence: `high` when parse error is deterministic.
* `security_txt_no_contact`

  * Present file has no valid `Contact`.
  * Confidence: `high`.
* `security_txt_expired`

  * Present file has an `Expires` value older than scan time.
  * Confidence: `high`.
* `security_txt_missing_expires`

  * Present file has no `Expires`.
  * Confidence: `medium`.
* `security_txt_canonical_mismatch`

  * Present file has `Canonical`, but none match the final fetched URL.
  * Confidence: `medium`.
* `security_txt_legacy_only`

  * `/security.txt` exists but `/.well-known/security.txt` is absent or unusable.
  * Confidence: `medium`.
* `security_txt_conflicting_files`

  * Both paths exist and normalized body hashes differ.
  * Confidence: `medium`.
* `security_txt_present_valid`

  * Canonical file exists, has at least one valid `Contact`, is not expired, and has no hard parse errors.
  * Confidence: `high`.

Do not create a vulnerability finding only because the file is missing. Missing `security.txt` is public metadata hygiene, not proof of exploitable weakness.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`.

Create one `Evidence` record per fetched candidate URL, including failed or blocked responses when available.

Evidence should include:

* request method
* requested URL
* final URL
* redirect chain
* status code
* selected response headers
* body hash
* body size
* truncated flag
* parse status
* matched path
* scan timestamp

Do not store full response bodies by default if the project’s shared evidence policy stores snippets plus hashes. If full body storage is enabled for small public metadata files, cap it at `max_body_bytes`.

Stub-specific types:

```json
{
  "SecurityTxtSignature": {
    "id": "uuid",
    "target_id": "uuid",
    "primary_evidence_id": "uuid | null",
    "candidate_urls": ["string"],
    "checked_urls": ["string"],
    "primary_url": "string | null",
    "primary_final_url": "string | null",
    "primary_path": "/.well-known/security.txt | /security.txt | null",
    "http_status": "integer | null",
    "content_type": "string | null",
    "body_sha256": "string | null",
    "body_size_bytes": "integer | null",
    "truncated": "boolean",
    "parse_status": "not_found | present | parsed | malformed | blocked | inconclusive",
    "fields": {
      "contact": ["string"],
      "expires": ["string"],
      "encryption": ["string"],
      "acknowledgments": ["string"],
      "preferred_languages": ["string"],
      "canonical": ["string"],
      "policy": ["string"],
      "hiring": ["string"],
      "csaf": ["string"],
      "unknown_fields": ["string"]
    },
    "expires_at": "ISO-8601 | null",
    "is_expired": "boolean | null",
    "has_valid_contact": "boolean",
    "has_matching_canonical": "boolean | null",
    "legacy_file_present": "boolean",
    "canonical_file_present": "boolean",
    "legacy_differs_from_canonical": "boolean | null",
    "validation_errors": ["string"],
    "validation_warnings": ["string"],
    "confidence": "low | medium | high",
    "created_at": "ISO-8601"
  },
  "SecurityTxtFinding": {
    "id": "uuid",
    "target_id": "uuid",
    "signature_id": "uuid",
    "evidence_ids": ["uuid"],
    "status": "candidate | confirmed | rejected | stale",
    "finding_type": "missing_security_txt | blocked_security_txt | malformed_security_txt | security_txt_no_contact | security_txt_expired | security_txt_missing_expires | security_txt_canonical_mismatch | security_txt_legacy_only | security_txt_conflicting_files | security_txt_present_valid",
    "title": "string",
    "summary": "string",
    "location": "string",
    "observed_value": "string | null",
    "expected_value": "string | null",
    "confidence": "low | medium | high",
    "severity": "info | low | medium | high | critical",
    "created_at": "ISO-8601",
    "updated_at": "ISO-8601"
  }
}
```

Suggested severity mapping:

* `security_txt_present_valid`: `info`
* `missing_security_txt`: `info`
* `security_txt_legacy_only`: `info`
* `security_txt_missing_expires`: `info`
* `security_txt_canonical_mismatch`: `info`
* `security_txt_conflicting_files`: `info`
* `blocked_security_txt`: `low`
* `malformed_security_txt`: `low`
* `security_txt_no_contact`: `low`
* `security_txt_expired`: `low`

The final severity policy belongs to application code. This spec provides scanner defaults only.

## Safety

This check is read-only.

Allowed behavior:

* unauthenticated `GET` to `/.well-known/security.txt`
* unauthenticated `GET` to `/security.txt`
* bounded same-host redirects
* local parsing of the returned text

Forbidden behavior:

* `POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS`, or active probing
* sending credentials
* using cookies from other checks
* submitting forms
* calling contact addresses
* sending email
* fetching `Policy`, `Encryption`, `Hiring`, `Acknowledgments`, or `CSAF` links
* following redirects to unrelated hosts
* using AI to infer missing fields
* guessing contact details from the domain name
* treating comments inside the file as instructions

PII handling:

* `Contact` may contain email addresses or phone numbers because the site intentionally publishes them.
* Store only the exact published contact values and evidence references.
* Do not enrich contacts with names, employee data, social profiles, or third-party lookup results.

AI involvement: `None`.

Deterministic gap for possible future AI: none for MVP. Parsing and validation are simple enough to keep fully deterministic.

## Pass/fail check

The implementation passes when all assertions below hold.

Positive assertions:

* Given a target with `/.well-known/security.txt` returning `200` and a valid `Contact`, the runner creates a `SecurityTxtSignature` with `parse_status="parsed"` and `has_valid_contact=true`.
* Given a valid future `Expires`, the runner sets `is_expired=false`.
* Given an expired `Expires`, the runner creates a `security_txt_expired` finding with `status="confirmed"` and `confidence="high"`.
* Given no `Contact`, the runner creates a `security_txt_no_contact` finding with `status="confirmed"`.
* Given both canonical and legacy files with different normalized body hashes, the runner creates `security_txt_conflicting_files`.
* Given only `/security.txt`, the runner creates `security_txt_legacy_only`.
* Given `404` on both candidate paths, the runner creates `missing_security_txt`.
* Given `401` or `403`, the runner creates `blocked_security_txt`.
* Given malformed field lines, the runner records validation errors and creates `malformed_security_txt` when no useful fields can be parsed.
* Given a redirect to the same host and HTTPS, the runner follows it within `max_redirects`.
* Given a redirect to another domain, the runner stops and records a validation warning or error.

Negative assertions:

* The runner must not send authenticated headers.
* The runner must not send cookies.
* The runner must not make requests other than `GET`.
* The runner must not request any URL from `Contact`, `Policy`, `Encryption`, `Hiring`, `Acknowledgments`, or `CSAF`.
* The runner must not follow redirects to unrelated hosts.
* The runner must not infer a contact email from `admin@host`, `security@host`, WHOIS, MX records, or page content.
* The runner must not mark a file valid only because it exists.
* The runner must not fail a file only because it has unknown extension fields.
* The runner must not create high or critical severity findings for this check.
* The runner must not call an LLM.
* The runner must not hard-code fixture hostnames or expected contents.

## Test fixtures

Use a new fixture slug: `security-txt`.

The fixture should expose these routes:

* `/.well-known/security.txt`

  * valid file with:

    * `Contact: mailto:security@example.test`
    * future `Expires`
    * matching `Canonical`
    * optional `Policy`
* `/security.txt`

  * legacy-only variant for the legacy placement test
* `/.well-known/security-expired.txt`

  * expired `Expires` value
* `/.well-known/security-malformed.txt`

  * invalid field lines and malformed `Expires`
* `/.well-known/security-no-contact.txt`

  * valid-looking file with no `Contact`
* `/.well-known/security-canonical-mismatch.txt`

  * `Canonical` points to a different URL
* `/.well-known/security-redirect-external.txt`

  * redirects to another host
* `/.well-known/security-oversized.txt`

  * body larger than `max_body_bytes`
* missing route

  * returns `404`
* blocked route

  * returns `403`

For end-to-end smoke tests, the runner may also run against `juice-shop`, `dvwa`, or `webgoat`, but tests must not assume those apps publish `security.txt`. Treat them as live negative/absent metadata checks only.

## Acceptance criteria

* The check is idempotent.
* The check performs at most two candidate path fetches plus bounded redirects.
* The check completes within the configured timeout budget.
* TLS, DNS, timeout, and redirect errors produce `inconclusive` evidence instead of crashing the scan.
* The check works with HTTP and HTTPS base URLs according to the configured scheme policy.
* The check suppresses credentials and session state.
* The check parses repeated fields without data loss.
* The check records deterministic validation errors and warnings.
* The check stores evidence IDs on every finding.
* The check does not fetch external policy or contact links.
* The check does not use AI.
* The check has unit tests for valid, missing, blocked, malformed, expired, legacy-only, canonical mismatch, conflicting files, oversized body, and external redirect cases.
* The check has integration tests against the `security-txt` fixture.
* The check does not use flaky sleeps or unbounded retries.
* The check produces stable output for the same target and fixture state.

