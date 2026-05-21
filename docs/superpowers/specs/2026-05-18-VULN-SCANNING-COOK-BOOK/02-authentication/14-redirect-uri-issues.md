---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 2
spec: 14
slug: redirect-uri-issues
status: done     # pending | in-progress | blocked | done
fixture: oauth-lab        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 2.14 Redirect URI issues

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

Detect OAuth/OIDC redirect URI validation weaknesses where an authorization endpoint accepts an attacker-controlled `redirect_uri`, a malformed variant of a trusted URI, or a URI on the wrong origin. A runner cares because weak validation can leak authorization codes, access tokens, or login errors to an untrusted destination.

## Inputs

The runner receives the shared `ScanTarget` plus optional OAuth/SSO scan settings.

### Required

* `ScanTarget`

  * Base URL.
  * Scope rules.
  * TLS policy.
  * Request timeout.
  * User-agent policy.
  * Evidence retention policy.

### Optional config

* `authorization_endpoints`: known OAuth/OIDC authorization URLs.
* `oidc_discovery_paths`: defaults:

  * `/.well-known/openid-configuration`
  * `/.well-known/oauth-authorization-server`
* `client_ids`: client IDs approved for this scan.
* `known_redirect_uris`: redirect URIs approved for this scan.
* `scanner_redirect_origin`: scanner-controlled or inert origin used for probes.

  * Default: `https://scanner.invalid`
  * Must not be a real third-party domain unless the operator explicitly configured and owns it.
* `max_authorization_endpoints`: default `5`.
* `max_redirect_uri_probes_per_endpoint`: default `8`.
* `allow_pre_auth_redirect_probe`: default `false`.
* `collect_login_page_links`: default `true`.
* `follow_redirects`: must be `false`.
* `body_snippet_bytes`: default `4096`.

### Credential handling

Credentials are not required and must not be used by this stub by default.

If credentials are present in the shared scan context, this stub must not submit them, must not complete SSO login, and must not approve consent screens. This check is pre-auth only.

## Detection logic

Detection is deterministic and split into passive discovery and optional pre-auth probes.

### 1. Discover OAuth/OIDC authorization endpoints

The runner should collect candidate authorization endpoints from response evidence.

Use only in-scope URLs unless the scan config explicitly allows an external identity provider URL.

Sources:

* OIDC metadata:

  * `GET /.well-known/openid-configuration`
  * `GET /.well-known/oauth-authorization-server`
* HTML and JavaScript from the target origin:

  * links with `client_id=`
  * links with `redirect_uri=`
  * links with `response_type=code`
  * paths containing `/authorize`, `/oauth/authorize`, `/connect/authorize`, `/sso`, or `/login`
* Existing crawler evidence from earlier phases, if available.

Do not infer technology from hostname. Detect OAuth/OIDC behavior from response fields, URLs, parameters, headers, and metadata.

A candidate authorization endpoint is usable when at least one of these is true:

* OIDC metadata has an `authorization_endpoint`.
* A URL has `client_id` and either `redirect_uri` or `response_type`.
* A same-origin login page links to an OAuth/OIDC-looking authorization URL.

### 2. Build a baseline request

For each authorization endpoint, build a baseline authorization request only when the runner has enough data.

Required baseline fields:

* `client_id`
* `response_type=code`
* `redirect_uri`
* `state`

Optional fields copied from observed evidence when present and safe:

* `scope`
* `audience`
* `resource`
* `code_challenge`
* `code_challenge_method`

Rules:

* Prefer values observed from target-owned pages.
* Prefer `known_redirect_uris` from config over values scraped from pages.
* Generate a unique random `state`.
* Do not include usernames, passwords, session cookies, access tokens, refresh tokens, ID tokens, or authorization codes.
* Do not send POST requests.
* Do not follow redirects.

If `client_id` or a baseline `redirect_uri` is missing, persist a low-confidence `candidate` signature only when passive evidence strongly suggests OAuth/SSO but the runner cannot safely test validation.

### 3. Generate redirect URI mutations

Only run mutations when `allow_pre_auth_redirect_probe=true`.

Generate a small fixed set of malformed redirect URIs from a known valid redirect URI and the configured `scanner_redirect_origin`.

Use at most `max_redirect_uri_probes_per_endpoint` mutations per endpoint.

Mutation classes:

| Class              | Example shape                                              | Purpose                                               |
| ------------------ | ---------------------------------------------------------- | ----------------------------------------------------- |
| foreign_origin     | `https://scanner.invalid/oauth-callback`                   | Detect acceptance of a fully untrusted origin.        |
| host_suffix        | `https://trusted.example.scanner.invalid/oauth-callback`   | Detect unsafe prefix or substring host matching.      |
| host_prefix        | `https://scanner.invalid/trusted.example/oauth-callback`   | Detect unsafe substring matching across the full URI. |
| scheme_downgrade   | `http://trusted.example/oauth-callback`                    | Detect HTTPS-to-HTTP downgrade acceptance.            |
| path_prefix        | `https://trusted.example/oauth-callback.evil`              | Detect unsafe path prefix matching.                   |
| path_traversal     | `https://trusted.example/oauth-callback/../evil`           | Detect path normalization mistakes.                   |
| encoded_host       | `https://trusted.example%2escanner.invalid/oauth-callback` | Detect decoding-before-validation mistakes.           |
| userinfo_confusion | `https://trusted.example@scanner.invalid/oauth-callback`   | Detect authority parsing mistakes.                    |

The runner must not include payloads that attempt token theft, phishing, account takeover, or credential capture. The probe URI is only a marker for validation behavior.

### 4. Send pre-auth validation probes

For each mutation:

* Send `GET` to the authorization endpoint.
* Use `allow_redirects=false`.
* Do not send cookies unless they are already part of a safe unauthenticated baseline request.
* Do not authenticate.
* Do not submit forms.
* Do not click consent.
* Do not request `response_type=token`.
* Prefer `response_type=code`.
* Add a fresh `state` marker per probe.

Record evidence for:

* Request URL with sensitive query values redacted where needed.
* Status code.
* `Location` header, if present.
* Response content type.
* Small body snippet.
* OAuth error fields from URL, JSON, or HTML.
* Whether the mutated redirect URI appears in `Location`, body, form action, hidden input, script, or meta refresh.

### 5. Classify outcomes

Create one finding per authorization endpoint and validation weakness class.

#### Confirmed

Set `status=confirmed` and `confidence=high` when a pre-auth response proves the endpoint accepts or uses an untrusted redirect URI.

Any of these is enough:

* Response is `3xx` and `Location` points to the mutated foreign origin.
* Response is `3xx` and `Location` points to a malformed trusted-looking URI whose effective origin is untrusted.
* Response body contains an auto-submitting form whose action points to the mutated foreign origin.
* Response body contains a meta refresh or JavaScript redirect to the mutated foreign origin.
* OAuth error is sent to the mutated foreign origin instead of being shown by the authorization server.

The runner must parse the effective URL origin using a real URL parser, not string matching.

#### Candidate

Set `status=candidate` when evidence suggests weak validation but does not prove redirect acceptance.

Examples:

* Login page is returned and the mutated `redirect_uri` is preserved in a hidden field.
* Login page is returned and the mutated `redirect_uri` appears in a continuation URL.
* Authorization endpoint does not reject an invalid redirect URI before login, but no redirect occurs.
* Passive evidence shows broad redirect URI patterns, such as wildcard-like configuration text, without a safe way to verify it.

Use `confidence=medium` when the evidence is clear but not conclusive. Use `confidence=low` when only passive hints exist.

#### Rejected

Set `status=rejected` when the endpoint clearly rejects the invalid redirect URI.

Examples:

* HTTP `400` or `403` with `invalid_redirect_uri`, `redirect_uri_mismatch`, `invalid_request`, or equivalent.
* Error page from the authorization server that does not redirect to the mutated URI.
* Login page is returned, but the mutated redirect URI is not preserved, echoed, or used.
* Request is blocked by scope rules before reaching the authorization endpoint.

Use `confidence=high` only when the rejection is explicit.

#### Stale

Set `status=stale` when previously stored evidence no longer matches current behavior.

Examples:

* Authorization endpoint no longer exists.
* Client ID is no longer accepted.
* Previously accepted invalid redirect URI is now rejected.
* Target moved to a new SSO flow and old evidence cannot be reproduced.

### 6. Evidence handling

Store small, audit-ready evidence. Do not store full login pages unless the shared evidence policy requires it.

For each probe, capture:

* Evidence ID.
* Authorization endpoint.
* Mutation class.
* Mutated redirect URI origin.
* Status code.
* Parsed `Location` origin, if any.
* OAuth error code, if any.
* Body snippet hash.
* Body snippet excerpt with secrets redacted.
* Timestamp.
* Request method.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Define only the stub-specific types below.

```typescript
export type RedirectUriIssueMutationClass =
  | "foreign_origin"
  | "host_suffix"
  | "host_prefix"
  | "scheme_downgrade"
  | "path_prefix"
  | "path_traversal"
  | "encoded_host"
  | "userinfo_confusion"
  | "passive_only";

export type RedirectUriIssueValidationResult =
  | "accepted_untrusted_redirect"
  | "preserved_untrusted_redirect"
  | "rejected_invalid_redirect"
  | "not_tested"
  | "inconclusive";

export interface RedirectUriIssueSignature {
  id: string;
  target_id: string;
  authorization_endpoint: string;
  client_id_hash?: string;
  baseline_redirect_uri_hash?: string;
  mutation_class: RedirectUriIssueMutationClass;
  mutated_redirect_origin?: string;
  request_method: "GET";
  response_status?: number;
  location_origin?: string;
  oauth_error?: string;
  validation_result: RedirectUriIssueValidationResult;
  evidence_ids: string[];
  first_seen_at: string;
  last_seen_at: string;
}

export interface RedirectUriIssueFinding {
  id: string;
  target: ScanTarget;
  signature: RedirectUriIssueSignature;
  evidence: Evidence[];
  title: string;
  status: "candidate" | "confirmed" | "rejected" | "stale";
  severity: "info" | "low" | "medium" | "high" | "critical";
  confidence: "low" | "medium" | "high";
  affected_authorization_endpoint: string;
  affected_client_id_hash?: string;
  weakness: RedirectUriIssueMutationClass;
  summary: string;
  remediation: string;
  detected_at: string;
}
```

### Severity guidance

The application owns final severity.

Suggested deterministic defaults:

| Condition                                               | Severity |
| ------------------------------------------------------- | -------- |
| Confirmed redirect to foreign origin before auth        | high     |
| Confirmed OAuth error redirect to foreign origin        | medium   |
| Candidate preserved invalid redirect through login page | medium   |
| Passive-only weak pattern                               | low      |
| Explicit rejection                                      | info     |

Do not set `critical` unless the shared severity policy has a rule that maps this condition to critical impact.

## Safety

This stub is read-only at the account and data level. It sends HTTP `GET` requests only.

### Allowed

* Fetch OAuth/OIDC metadata.
* Parse same-origin login links.
* Send unauthenticated authorization requests with mutated `redirect_uri` values.
* Stop at the first response.
* Capture headers, status, redirect target, and a small redacted body snippet.

### Not allowed

* No password submission.
* No MFA submission.
* No consent approval.
* No token exchange.
* No use of authorization codes.
* No `response_type=token` or implicit-flow token capture.
* No credential stuffing.
* No brute force.
* No open redirect chaining through unrelated endpoints.
* No following redirects to third-party origins.
* No requests to scanner-observed arbitrary URLs from page content.
* No POST, PUT, PATCH, or DELETE.
* No browser automation that clicks through login or consent.

### Redirect discipline

* `follow_redirects` must be `false`.
* A `Location` header may be parsed but not followed when it points outside scope.
* The runner may follow same-origin redirects only for passive discovery and only if the shared crawler policy allows it.
* The runner must not request a real third-party callback unless it is configured as scanner-owned.

### PII and secret handling

* Redact cookies, access tokens, ID tokens, refresh tokens, authorization codes, passwords, and email addresses from evidence snippets.
* Store client IDs as hashes unless the shared persistence layer treats them as non-sensitive scan metadata.
* Store redirect URI hashes for baseline trusted URIs.
* Store mutated redirect origin and mutation class, not full sensitive query strings.
* Do not log full authorization URLs when they contain sensitive parameters.

### AI involvement

AI: `None`.

No AI is needed because endpoint discovery, URL mutation, response parsing, and classification are deterministic.

Deterministic gap: Some providers validate `redirect_uri` only after login. In that case the runner must return `candidate` or `inconclusive`; it must not ask AI to infer exploitability.

## Pass/fail check

The implementation passes when all assertions below are true.

### Discovery assertions

* The runner fetches OIDC metadata from configured discovery paths when in scope.
* The runner extracts `authorization_endpoint` from valid OIDC JSON.
* The runner extracts candidate authorization URLs from same-origin HTML and JavaScript evidence.
* The runner does not assume a technology stack from hostname, favicon, page title, or vendor-looking path.
* The runner does not create an authorization probe without a `client_id`.
* The runner does not create an authorization probe without a baseline redirect URI unless config explicitly allows passive-only reporting.

### Probe assertions

* The runner sends only `GET` requests.
* The runner sets `allow_redirects=false`.
* The runner generates a fresh `state` value per probe.
* The runner limits probes to `max_redirect_uri_probes_per_endpoint`.
* The runner uses a real URL parser to compare effective origins.
* The runner classifies a `3xx Location` to `https://scanner.invalid/...` as `confirmed` with `confidence=high`.
* The runner classifies `invalid_redirect_uri` or equivalent authorization-server error as `rejected`.
* The runner classifies a login page that preserves the mutated redirect URI but does not redirect as `candidate`, not `confirmed`.
* The runner stores evidence IDs on every finding.

### Negative assertions

* The runner must not follow an off-scope redirect.
* The runner must not submit credentials.
* The runner must not approve consent.
* The runner must not exchange authorization codes.
* The runner must not request `response_type=token`.
* The runner must not store access tokens, ID tokens, refresh tokens, passwords, or session cookies in finding fields.
* The runner must not mark passive-only wildcard hints as `confirmed`.
* The runner must not mark a provider as vulnerable only because it returns a login page.
* The runner must not hard-code hostname-to-provider assumptions.
* The runner must not retry many redirect variants after a clear explicit rejection when the probe budget is exhausted.
* The runner must not use AI to decide whether a redirect URI was accepted.

### Persistence assertions

* `RedirectUriIssueSignature.evidence_ids` is non-empty for every persisted finding.
* `RedirectUriIssueFinding.confidence` is one of `low`, `medium`, or `high`.
* `RedirectUriIssueFinding.status` is one of `candidate`, `confirmed`, `rejected`, or `stale`.
* `request_method` is always `GET`.
* `validation_result` matches the observed response behavior.
* Re-running the scan updates `last_seen_at` for the same signature instead of creating duplicates.

## Test fixtures

Use a new fixture: `oauth-redirect-uri-lab`.

The fixture should expose a small OAuth/OIDC-like authorization server inside the test container. It does not need real login, token issuance, or user accounts.

### Fixture routes

| Route                                | Behavior                                                                               |
| ------------------------------------ | -------------------------------------------------------------------------------------- |
| `/.well-known/openid-configuration`  | Returns JSON with `authorization_endpoint`.                                            |
| `/oauth/authorize/strict`            | Rejects unknown redirect URIs with `invalid_redirect_uri`.                             |
| `/oauth/authorize/loose-host-prefix` | Incorrectly accepts host-prefix or host-suffix tricks.                                 |
| `/oauth/authorize/loose-path-prefix` | Incorrectly accepts path-prefix tricks.                                                |
| `/oauth/authorize/preserves-invalid` | Returns login HTML that keeps invalid `redirect_uri` in a hidden field.                |
| `/oauth/authorize/foreign-origin`    | Incorrectly redirects to a fully foreign origin.                                       |
| `/login`                             | Contains a sample SSO link with `client_id`, `response_type=code`, and `redirect_uri`. |

### Fixture data

Use:

* Client ID: `test-client`
* Valid redirect URI: `https://app.example.test/oauth/callback`
* Scanner probe origin: `https://scanner.invalid`

The fixture must not issue real authorization codes or tokens. If a redirect needs a code-like value for realism, use a fixed inert marker such as `code=fixture-code-not-valid`.

### Expected fixture outcomes

| Fixture route                        | Expected status | Expected confidence |
| ------------------------------------ | --------------- | ------------------- |
| `/oauth/authorize/strict`            | rejected        | high                |
| `/oauth/authorize/loose-host-prefix` | confirmed       | high                |
| `/oauth/authorize/loose-path-prefix` | confirmed       | high                |
| `/oauth/authorize/preserves-invalid` | candidate       | medium              |
| `/oauth/authorize/foreign-origin`    | confirmed       | high                |

### Existing public fixtures

`juice-shop`, `dvwa`, and `webgoat` are not good primary fixtures for this stub unless the project adds a controlled OAuth/SSO module around them. Use them only for passive discovery regression tests, not confirmed redirect URI findings.

## Acceptance criteria

* The stub is idempotent: the same endpoint, client ID hash, and mutation class produce the same signature ID.
* The stub respects target scope and does not follow off-scope redirects.
* The stub completes within the configured probe budget.
* The stub handles TLS errors, DNS errors, connection resets, timeouts, malformed URLs, malformed JSON, and invalid percent-encoding without crashing.
* The stub records clear rejected findings for explicit `invalid_redirect_uri` behavior when the project stores negative evidence.
* The stub records no finding, or an `info` rejected finding, when OAuth/SSO is absent and project policy allows negative evidence.
* The stub avoids flaky retries: at most one retry for transient network errors per endpoint, and no retry for deterministic `400`, `401`, `403`, or valid OAuth error responses.
* The stub stores redacted evidence only.
* The stub never stores credentials, cookies, tokens, authorization codes, or full sensitive query strings.
* The stub does not require AI.
* Unit tests cover URL parsing, mutation generation, origin comparison, OAuth error parsing, redirect handling, passive-only classification, rejected classification, confirmed classification, and stale update behavior.
* Integration tests run against `oauth-redirect-uri-lab` without external network access.
* Documentation explains that confirmed findings require a pre-auth redirect or equivalent deterministic proof, while post-login-only validation gaps remain candidates unless tested through an approved manual workflow.

