---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 1
spec: 20
slug: env
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 1.20 `.env`

> Phase 1 — Information gathering · Category: Sensitive files

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

Detect publicly reachable `.env` and related environment files that may expose application secrets, database credentials, API tokens, framework configuration, debug flags, or cloud keys. A runner cares because these files are often enough to turn a passive finding into full account, database, or infrastructure compromise.

## Inputs

The runner receives a shared `ScanTarget` from `../00-shared-schema.md`.

Required input:

* `target.base_url`: root URL used to resolve candidate `.env` paths.

Optional inputs:

* `target.allowed_paths`: scope restriction. If present, only test paths inside this allowlist.
* `target.disallowed_paths`: paths that must not be requested.
* `target.credentials`: optional authenticated context from the shared runner. This check must not require credentials, but may run in an authenticated browser/session if the scan mode already provides one.
* `max_bytes_per_response`: default `65536`.
* `request_timeout_ms`: default from shared HTTP client.
* `candidate_paths`: optional override or extension of the default path list.
* `follow_redirects`: default `false`.
* `user_agent`: default shared scanner user agent.
* `respect_robots_txt`: use the project default for passive/content discovery checks.
* `rate_limit`: use shared runner budget and per-host pacing.

Default candidate paths:

```text
/.env
/.env.local
/.env.dev
/.env.development
/.env.test
/.env.testing
/.env.stage
/.env.staging
/.env.prod
/.env.production
/.env.backup
/.env.bak
/.env.old
/.env.save
/.env.example
/.env.dist
/.env.sample
/api/.env
/app/.env
/backend/.env
/config/.env
/server/.env
```

Notes:

* `.env.example`, `.env.dist`, and `.env.sample` are lower risk unless real secrets are present.
* Do not generate host-specific expected paths.
* Do not crawl arbitrary directories for more `.env` names in this stub. Use only configured candidate paths.

## Detection logic

Use deterministic HTTP checks only.

### Request method

For each candidate path:

1. Build the URL by resolving the path against `ScanTarget.base_url`.
2. Skip the request if the path is outside `allowed_paths` or inside `disallowed_paths`.
3. Send a `GET` request.
4. Set `Range: bytes=0-65535` when the shared HTTP client supports it.
5. Do not follow redirects by default.
6. Store response metadata and a redacted body excerpt in shared `Evidence`.

Do not use `POST`, `PUT`, `PATCH`, `DELETE`, or application-specific actions.

### Response eligibility

A response is eligible for `.env` detection when all of these are true:

* HTTP status is `200`.
* The final URL path still looks like a requested `.env` candidate when redirects are disabled.
* Body length after decompression is greater than zero.
* Body is text-like.
* Body does not look like a normal HTML error page, SPA shell, login page, WAF page, or CDN error page.

Treat these as non-evidence for exposed `.env` unless positive `.env` patterns are also present:

* `text/html` with `<html`, `<!doctype html`, `<script`, or `<app-root`.
* JSON API error bodies such as `{"error": "not found"}`.
* Generic 200 fallback pages with the same hash as `/`, `/404`, or a known SPA route.
* Login redirects or authentication forms.
* Directory listings that mention `.env` but do not return file contents.

### Positive body patterns

Mark a response as `.env-like` when it contains at least two environment assignment lines.

Assignment line pattern:

```regex
(?m)^\s*(?:export\s+)?[A-Z_][A-Z0-9_]{1,80}\s*=\s*(?:"[^"\r\n]*"|'[^'\r\n]*'|[^\s#\r\n][^\r\n]*)?\s*(?:#.*)?$
```

Common high-signal keys:

```regex
(?im)^\s*(?:export\s+)?(?:APP_KEY|APP_SECRET|SECRET_KEY|DJANGO_SECRET_KEY|DATABASE_URL|DB_PASSWORD|DB_PASS|MYSQL_PASSWORD|POSTGRES_PASSWORD|REDIS_URL|REDIS_PASSWORD|JWT_SECRET|SESSION_SECRET|COOKIE_SECRET|API_KEY|API_SECRET|PRIVATE_KEY|AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|AZURE_CLIENT_SECRET|GOOGLE_APPLICATION_CREDENTIALS|OPENAI_API_KEY|STRIPE_SECRET_KEY|GITHUB_TOKEN|GITLAB_TOKEN|SENTRY_DSN)\s*=
```

Secret-looking value patterns:

```regex
(?i)\b(?:sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9_]{20,}|glpat-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16})\b
```

```regex
(?im)^\s*(?:export\s+)?[A-Z_][A-Z0-9_]{1,80}\s*=\s*(?:"[^"\r\n]{12,}"|'[^'\r\n]{12,}'|[^\s#\r\n]{12,})\s*(?:#.*)?$
```

### Classification

Use these deterministic outcomes:

* `confirmed`, `high confidence`: status `200`, text-like body, at least two environment assignment lines, and at least one high-signal key or secret-looking value.
* `candidate`, `medium confidence`: status `200`, text-like body, at least two environment assignment lines, but only low-signal keys such as `APP_ENV`, `NODE_ENV`, `DEBUG`, `PORT`, or placeholder values.
* `candidate`, `low confidence`: status `200`, text-like body, one environment assignment line plus strong contextual evidence from the requested path and content type, but no secret-looking value.
* `rejected`: not found, forbidden, redirect, non-text body, fallback page, login page, or body lacks `.env` assignment syntax.
* `stale`: a previously confirmed finding is no longer reproducible after the configured stale-check window.

### Confidence rules

Set confidence from evidence, not hostnames or framework guesses.

`high`:

* The body contains real `.env` syntax and at least one likely secret, credential, DSN, database URL, private key reference, or cloud token key.

`medium`:

* The body is clearly an environment file, but values are placeholders, examples, or non-sensitive configuration.

`low`:

* The response may be a partial environment file, truncated file, or generated config, but lacks enough sensitive markers.

### Severity hint

The stub may emit a severity hint, but final severity policy is owned by the shared scanner.

Suggested hint:

* `high` when confirmed and secrets or credential-like values are present.
* `medium` when confirmed but values look like placeholders or non-sensitive config.
* `low` for weak candidates.
* `info` for intentionally public `.env.example`, `.env.dist`, or `.env.sample` files with placeholders only.

### Evidence handling

For each eligible response, store:

* requested URL
* candidate path
* HTTP status
* final URL
* redirect count
* response headers needed for audit
* content type
* body hash
* response size
* truncation flag
* matched key names
* matched line numbers
* redacted excerpt

Redact values before storing excerpts. Keep variable names and line numbers.

Example redaction:

```text
DATABASE_URL=<redacted>
APP_KEY=<redacted>
DEBUG=true
```

Do not store full secrets in logs, reports, or finding summaries.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Define only `.env`-specific types.

```typescript
export type EnvConfidence = "low" | "medium" | "high";
export type EnvFindingStatus = "candidate" | "confirmed" | "rejected" | "stale";

export type EnvPathRisk = "sample" | "runtime" | "backup" | "unknown";

export interface EnvSignature {
  id: string;
  name: string;
  path: string;
  path_risk: EnvPathRisk;
  method: "GET";
  max_bytes: number;
  follow_redirects: false;
  expected_statuses: number[];
  assignment_regex: string;
  high_signal_key_regexes: string[];
  secret_value_regexes: string[];
  negative_body_regexes: string[];
  min_assignment_lines: number;
}

export interface EnvMatchedVariable {
  name: string;
  line_number: number;
  value_redacted: true;
  key_signal: "low" | "high";
  value_signal: "none" | "placeholder" | "secret_like";
}

export interface EnvFinding {
  target: ScanTarget;
  status: EnvFindingStatus;
  confidence: EnvConfidence;
  severity_hint: "info" | "low" | "medium" | "high";
  signature_id: string;
  requested_url: string;
  final_url: string;
  path: string;
  path_risk: EnvPathRisk;
  http_status: number;
  content_type?: string;
  body_sha256: string;
  response_size_bytes: number;
  response_truncated: boolean;
  matched_variables: EnvMatchedVariable[];
  matched_secret_indicators: string[];
  evidence: Evidence[];
  reason: string;
  remediation: string;
}
```

Recommended built-in signatures:

```typescript
export const ENV_SIGNATURES: EnvSignature[] = [
  {
    id: "env-root-runtime",
    name: "Root runtime .env file",
    path: "/.env",
    path_risk: "runtime",
    method: "GET",
    max_bytes: 65536,
    follow_redirects: false,
    expected_statuses: [200],
    assignment_regex: String.raw`(?m)^\s*(?:export\s+)?[A-Z_][A-Z0-9_]{1,80}\s*=\s*(?:"[^"\r\n]*"|'[^'\r\n]*'|[^\s#\r\n][^\r\n]*)?\s*(?:#.*)?$`,
    high_signal_key_regexes: [
      String.raw`(?i)^(APP_KEY|APP_SECRET|SECRET_KEY|DJANGO_SECRET_KEY|DATABASE_URL|DB_PASSWORD|DB_PASS|MYSQL_PASSWORD|POSTGRES_PASSWORD|REDIS_URL|REDIS_PASSWORD|JWT_SECRET|SESSION_SECRET|COOKIE_SECRET|API_KEY|API_SECRET|PRIVATE_KEY|AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|AZURE_CLIENT_SECRET|OPENAI_API_KEY|STRIPE_SECRET_KEY|GITHUB_TOKEN|GITLAB_TOKEN|SENTRY_DSN)$`
    ],
    secret_value_regexes: [
      String.raw`(?i)\b(sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9_]{20,}|glpat-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16})\b`,
      String.raw`(?i)^.{12,}$`
    ],
    negative_body_regexes: [
      String.raw`(?is)<html\b`,
      String.raw`(?is)<!doctype\s+html`,
      String.raw`(?is)<form\b[^>]*(login|signin|password)`,
      String.raw`(?i)\b404\b.*\bnot\s+found\b`,
      String.raw`(?i)\baccess\s+denied\b`
    ],
    min_assignment_lines: 2
  }
];
```

Persistence rules:

* Persist one finding per exposed URL/path.
* Link every finding to at least one `Evidence` record.
* Store redacted excerpts only.
* Store hashes for deduplication and stale checks.
* If multiple candidate paths return the same body hash, keep separate evidence records but deduplicate summary output where the project pattern supports it.
* Do not persist raw secret values outside the secure evidence store, if one exists.
* If no secure evidence store exists, do not persist raw body content at all.

## Safety

This check is read-only.

Allowed:

* `GET` requests to explicit candidate paths.
* Optional `Range` header to limit response size.
* Response parsing and redaction.
* Hashing response bodies.
* Stale re-checks using the same read-only method.

Not allowed:

* `POST`, `PUT`, `PATCH`, `DELETE`, or other mutating methods.
* Path traversal payloads such as `../.env`.
* Recursive brute forcing.
* Wordlist expansion beyond configured candidate paths.
* Credential testing using exposed values.
* Calling third-party APIs with discovered keys.
* Database connection attempts.
* Cloud account validation.
* Secret verification.
* Writing tickets, comments, or reports directly from raw `.env` content.
* Logging raw secret values.

Payload restrictions:

* Use only safe URL paths.
* Do not include shell metacharacters, traversal sequences, encoded traversal, null bytes, or framework-specific exploit payloads.
* Do not attempt source disclosure through debug endpoints in this stub. That belongs in separate checks.

PII and secret handling:

* Treat all `.env` values as sensitive.
* Redact values before logging, persistence, report output, or LLM usage.
* Preserve variable names, line numbers, hashes, and short structural context.
* Do not print full connection strings.
* Do not include raw private keys, tokens, passwords, cookies, or API keys in finding text.

AI involvement:

* `None`.
* Detection, classification, redaction, and pass/fail logic are deterministic.
* If a future implementation uses AI to write remediation text, it must use redacted evidence only and must not affect status, confidence, or severity.

## Pass/fail check

The implementation passes when all assertions below are true.

### Positive assertions

Given a target where `GET /.env` returns `200` with:

```text
APP_ENV=production
DATABASE_URL=postgres://app:secret@example.internal:5432/app
JWT_SECRET=super-secret-value
```

The runner must:

* Create one `EnvFinding`.
* Set `status` to `confirmed`.
* Set `confidence` to `high`.
* Set `severity_hint` to `high`.
* Link the finding to at least one shared `Evidence` record.
* Record the requested URL and path.
* Record matched variable names: `APP_ENV`, `DATABASE_URL`, and `JWT_SECRET`.
* Redact all values in excerpts.
* Store body hash and response size.
* Mark `response_truncated` correctly.
* Complete without using AI.

Given `/.env.example` with placeholder-only values:

```text
APP_ENV=local
DATABASE_URL=postgres://user:password@localhost:5432/db
JWT_SECRET=change-me
```

The runner must:

* Create a finding with `status` `candidate` or `confirmed`, depending on project severity policy.
* Use no higher than `medium` confidence unless a real secret-looking value is present.
* Set `severity_hint` no higher than `medium`.
* Include `path_risk` as `sample`.

Given a previously confirmed finding where the same path later returns `404`:

* Mark the new observation as `rejected`.
* Mark the old finding as `stale` only through the shared stale-finding workflow.

### Negative assertions

The runner must not:

* Treat a `404`, `403`, `401`, `302`, or `500` response as confirmed.
* Treat a SPA fallback HTML page as `.env` exposure.
* Treat a login page as `.env` exposure.
* Treat a JSON error response as `.env` exposure.
* Treat a directory listing that only names `.env` as exposed file content.
* Follow redirects and classify the redirected page as `.env`.
* Infer `.env` exposure from hostname, framework, headers, favicon, or server banner.
* Hard-code a hostname to an expected technology or expected result.
* Store raw secret values in normal logs.
* Put raw `.env` values in finding summaries.
* Use exposed credentials to authenticate anywhere.
* Call external services to validate tokens.
* Generate additional unscoped paths.
* Send discovered secrets to an LLM.
* Retry endlessly after timeouts or TLS failures.
* Fail the whole scan when this check errors on one path.

### Error assertions

For TLS errors, timeouts, decompression errors, and oversized responses:

* Record a non-fatal check error using the shared runner error shape.
* Do not create a confirmed finding without body evidence.
* Continue with remaining candidate paths when budget allows.
* Respect retry limits from the shared HTTP client.

## Test fixtures

Use a new fixture slug: `env-exposure`.

The fixture should expose deterministic endpoints inside the test container.

Required routes:

```text
/.env
/.env.example
/.env.local
/.env.backup
/html-fallback/.env
/login-fallback/.env
/json-error/.env
/redirect-env
/large/.env
```

Fixture behavior:

* `/.env` returns `200 text/plain` with realistic `.env` syntax and redacted-safe fake secrets.
* `/.env.example` returns `200 text/plain` with placeholder values.
* `/.env.local` returns `403`.
* `/.env.backup` returns `200 text/plain` with at least two assignment lines and one fake secret-looking value.
* `/html-fallback/.env` returns `200 text/html` with an SPA shell.
* `/login-fallback/.env` returns `200 text/html` with a login form.
* `/json-error/.env` returns `200 application/json` with `{"error":"not found"}`.
* `/redirect-env` returns `302` to `/.env`; the scanner must not follow it by default.
* `/large/.env` returns a body larger than `max_bytes_per_response`; the scanner must truncate safely and still classify only from the retained slice.

Use fake secrets only. Do not include live-looking credentials that could be mistaken for real third-party keys.

Example fixture body for `/.env`:

```text
APP_ENV=production
APP_DEBUG=false
DATABASE_URL=postgres://app:redacted@example.internal:5432/app
JWT_SECRET=fake_jwt_secret_for_test_only
AWS_ACCESS_KEY_ID=AKIA0000000000000000
AWS_SECRET_ACCESS_KEY=fake_secret_for_test_only
```

Optional compatibility fixtures:

* `juice-shop`: use only as a negative target unless the test harness intentionally adds a mounted `.env`.
* `dvwa`: use only as a negative target unless the test harness intentionally adds a mounted `.env`.
* `webgoat`: use only as a negative target unless the test harness intentionally adds a mounted `.env`.

Do not require public internet access for tests.

## Acceptance criteria

The implementation is accepted when:

* It uses the shared `ScanTarget` and `Evidence` types without redefining them.
* It defines only `EnvSignature`, `EnvFinding`, and small supporting `.env`-specific types.
* It performs read-only `GET` requests against scoped candidate paths.
* It uses deterministic response evidence to classify findings.
* It handles `.env`, environment variants, backup variants, and sample variants.
* It avoids hostname, framework, or banner-based assumptions.
* It rejects fallback HTML, login pages, JSON errors, redirects, and non-text bodies.
* It redacts secret values before logs, persistence, summaries, reports, and any optional downstream text generation.
* It stores evidence IDs, hashes, matched variable names, line numbers, and redacted excerpts.
* It links each finding to shared evidence.
* It marks confidence as only `low`, `medium`, or `high`.
* It marks status as only `candidate`, `confirmed`, `rejected`, or `stale`.
* It has explicit tests for positive exposure, sample files, fallback pages, redirects, forbidden responses, oversized bodies, and stale behavior.
* It is idempotent: repeated scans over unchanged responses produce stable findings and evidence hashes.
* It completes within the shared phase budget.
* It respects per-host rate limits and retry caps.
* It treats TLS errors, timeouts, and parsing failures as non-fatal check errors.
* It does not call AI.
* It does not validate, reuse, or test any discovered secret.
* It does not log raw credentials.
* It does not perform flaky retries or network calls outside the target scope.

