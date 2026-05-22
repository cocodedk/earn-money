---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these
# six lines intact. Values below the comments are yours to change.
phase: 3
spec: 4
slug: broad-domain-scope
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
---

# 3.4 Broad domain scope

> Phase 3 — Session management · Category: Cookie weaknesses

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

Detect sensitive cookies scoped to an overly broad `Domain`. The runner cares because domain-scoped session cookies can be sent to sibling subdomains and may be overwritten by weaker or compromised subdomains, increasing the impact of subdomain takeover, mixed-trust hosting, or cookie tossing conditions.

## Inputs

The runner receives a shared `ScanTarget` and writes shared `Evidence` records. This stub does not redefine either type.

Required inputs:

* `target`: shared `ScanTarget`.
* `base_url`: normalized target origin from `ScanTarget`.
* `http_client`: shared HTTP client with redirect, TLS, timeout, and cookie-jar controls.
* `public_suffix_list`: project-approved PSL parser or equivalent domain-boundary helper.
* `scanner_config`: stub-specific knobs listed below.

Optional inputs:

* `authenticated_context`: existing scoped session from the project runner, if already available.
* `known_auth_endpoints`: previously discovered login/profile URLs.
* `prior_cookie_evidence`: cookie evidence collected by other checks.
* `allowed_cookie_domain_patterns`: organization-approved cookie domain scopes, if the program documents shared-session architecture.

Config knobs:

| Name | Default | Purpose |
| ---- | ------: | ------- |
| `enabled` | `true` | Allows this stub to run. |
| `request_timeout_ms` | `10000` | Per-request timeout. |
| `max_public_requests` | `4` | Maximum unauthenticated requests. |
| `max_authenticated_requests` | `4` | Maximum requests using an existing authenticated context. |
| `follow_redirects` | `true` | Capture redirect-chain cookies and the final response. |
| `flag_parent_domain_scope` | `true` | Flag sensitive cookies scoped above the exact response host. |
| `flag_apex_domain_scope` | `true` | Flag sensitive cookies using the registrable domain when host-only scope would work. |
| `redact_cookie_values` | `true` | Cookie values must be redacted before logs and findings. |

## Detection logic

Detection is deterministic and header-based.

### 1. Collect cookie evidence

Allowed unauthenticated requests:

1. `GET /`
2. `HEAD /` only if the shared runner already uses it for header collection.
3. Redirect responses while resolving `/`, up to the shared redirect limit.
4. `GET` a discovered login page when earlier phases already identified one.

Allowed authenticated requests, only when `authenticated_context` already exists:

1. `GET` the authenticated landing page supplied by the shared context.
2. `GET` the current-user/profile endpoint supplied by prior discovery.
3. `GET` one safe page that normally refreshes session cookies.

For every response, record the response host, scheme, status code, redirect position, and every `Set-Cookie` header as a separate parsed cookie.

### 2. Parse cookie scope

Use a standards-aware cookie parser and a public-suffix-aware hostname helper.

For each cookie, extract:

* `name`
* redacted or hashed `value`
* `domain`
* whether the cookie is host-only because `Domain` is absent
* canonical response host
* registrable domain for the response host
* `path`
* `secure`
* `httponly`
* `samesite`

Normalization rules:

* Compare hostnames case-insensitively.
* Strip a leading dot from `Domain` for comparison; modern cookie handling ignores the leading dot.
* Reject or classify as invalid any `Domain` equal to a public suffix, such as `com` or `co.uk`.
* Treat an absent `Domain` attribute as host-only and normally safe for this spec.
* Treat an explicit `Domain` equal to the response host as less broad than a parent domain, but still not host-only.

### 3. Classify cookie sensitivity

High-sensitivity cookies:

* Common session or auth names: `PHPSESSID`, `JSESSIONID`, `connect.sid`, `ASP.NET_SessionId`, `session`, `sid`, `auth`, `jwt`, `access_token`, `refresh_token`, `id_token`.
* Cookies set after login or on authenticated pages.
* Cookies with broad `Path=/` scope that appear to carry login state.

Medium-sensitivity cookies:

* Names containing `session`, `sess`, `auth`, `token`, `login`, `remember`, or `sso`.
* Cookies set by discovered login pages without authenticated confirmation.

Usually non-vulnerable cookies:

* Analytics, consent, locale, theme, experiment, or preference cookies.
* Load balancer affinity cookies unless project policy treats them as sensitive.
* Explicitly allowlisted shared-session cookies, unless the observed domain is broader than the allowlist.

### 4. Classify broad domain scope

Create findings only for high or medium sensitivity cookies.

| Observation | Status | Confidence |
| ----------- | ------ | ---------- |
| Sensitive cookie from `app.example.com` sets `Domain=example.com`. | `confirmed` | `high` |
| Sensitive cookie from `admin.eu.example.com` sets `Domain=.example.com`. | `confirmed` | `high` |
| Sensitive cookie from apex `example.com` explicitly sets `Domain=example.com` while `flag_apex_domain_scope=true`. | `candidate` | `medium` |
| Sensitive cookie sets `Domain` to the exact response host, such as `Domain=app.example.com`. | `candidate` | `low` |
| Sensitive cookie omits `Domain` and is host-only. | `rejected` | `high` |
| Cookie `Domain` is a public suffix or otherwise invalid and would be rejected by standards-compliant cookie handling. | `rejected` | `high` |
| Previous broad-domain finding no longer appears in current evidence. | `stale` | `medium` |

Do not create a finding for:

* Non-sensitive cookies.
* Host-only cookies.
* Cookies whose `Domain` matches an explicit allowlist and whose name/category is expected to be shared.
* Cookies from out-of-scope redirect destinations.
* Cookies synthesized by the scanner, browser automation framework, or proxy.

This spec does not prove exploitability. It does not check whether sibling subdomains are compromised, whether cookie tossing works, or whether a subdomain takeover exists.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Stub-specific types: `BroadDomainScopeSignature`, `BroadDomainScopeFinding`.

### `BroadDomainScopeSignature`

```ts
export interface BroadDomainScopeSignature {
  signature_id: string;
  cookie_name_pattern: string;
  match_type: "equals" | "contains" | "regex";
  cookie_category:
    | "session"
    | "auth"
    | "access_token"
    | "refresh_token"
    | "remember_me"
    | "framework_session"
    | "load_balancer"
    | "unknown";
  sensitivity: "low" | "medium" | "high";
  allowed_domain_pattern?: string;
  confidence: "low" | "medium" | "high";
  enabled: boolean;
  created_at: string;
  updated_at: string;
}
```

### `BroadDomainScopeFinding`

```ts
export interface BroadDomainScopeFinding {
  finding_id: string;
  target_id: string;
  evidence_ids: string[];

  cookie_name: string;
  cookie_value_fingerprint?: string;
  source_url: string;
  source_host: string;
  source_method: "GET" | "HEAD";
  source_status_code: number;
  source_context: "public" | "authenticated" | "redirect";

  observed_scope: {
    domain_attribute?: string;
    normalized_domain?: string;
    host_only: boolean;
    response_host: string;
    registrable_domain: string;
    path?: string;
    applies_to_parent_domain: boolean;
    applies_to_sibling_subdomains: boolean;
    public_suffix_invalid: boolean;
  };

  observed_attributes: {
    secure: boolean;
    httponly: boolean;
    samesite?: "Strict" | "Lax" | "None" | "missing" | "invalid";
  };

  cookie_category:
    | "session"
    | "auth"
    | "access_token"
    | "refresh_token"
    | "remember_me"
    | "framework_session"
    | "load_balancer"
    | "unknown";

  scope_issue:
    | "parent_domain"
    | "apex_domain"
    | "exact_host_domain_attribute"
    | "public_suffix_invalid";

  sensitivity: "low" | "medium" | "high";
  title: string;
  summary: string;
  remediation: {
    summary: string;
    steps: string[];
  };

  confidence: "low" | "medium" | "high";
  status: "candidate" | "confirmed" | "rejected" | "stale";
  safe: true;
  created_at: string;
  updated_at: string;
}
```

Evidence requirements:

* `source`: `cookie`
* `field`: `Set-Cookie`
* `matched_value`: cookie name and normalized domain, not the raw value
* `raw_excerpt`: redacted `Set-Cookie` header, for example `sid=<redacted>; Domain=.example.com; Path=/; Secure; HttpOnly`
* `content_hash`: hash of the redacted header or secure raw evidence hash

Recommended remediation:

* Omit `Domain` for sensitive cookies so the browser treats them as host-only.
* Scope session cookies to the narrowest host and path that still supports the product flow.
* Avoid sharing primary session cookies across mixed-trust subdomains.
* If cross-subdomain SSO is required, use a short-lived, purpose-specific handoff cookie instead of the main session cookie.

## Safety

This check is passive and read-only unless the shared runner supplies an already-authenticated context.

Allowed:

* `GET`
* `HEAD`
* Following redirects within configured limits
* Reading `Set-Cookie` response headers
* Public-suffix-aware hostname comparison
* Using an existing authenticated session to visit safe read-only pages

Not allowed:

* `POST`, `PUT`, `PATCH`, or `DELETE`
* Login attempts created by this spec
* Logout requests
* Cookie tossing or cookie injection
* Subdomain takeover checks
* DNS brute forcing
* Visiting arbitrary sibling subdomains to see whether cookies are sent
* Treating an allowlisted shared SSO cookie as vulnerable without additional evidence

PII and secrets:

* Never log raw cookie values.
* Redact `Set-Cookie` values in evidence excerpts and finding summaries.
* Store cookie fingerprints only with the project-approved secret hashing helper.
* Treat internal hostnames and subdomain names as sensitive metadata when project policy requires it.
* Do not send cookie evidence to AI.

AI involvement: `None`.

There is no deterministic gap that requires AI. Cookie parsing and domain-boundary analysis are deterministic.

## Pass/fail check

A coding agent implementation passes when these assertions hold.

Positive assertions:

* It accepts a shared `ScanTarget` and writes shared `Evidence`.
* It does not redefine shared `ScanTarget` or `Evidence`.
* It captures every `Set-Cookie` header as a separate cookie observation.
* It uses a public-suffix-aware domain helper.
* It treats an absent `Domain` attribute as host-only.
* It normalizes leading-dot domains, such as `.example.com` to `example.com`.
* It detects `sid=<value>; Domain=example.com; Path=/` set by `app.example.com` as broad domain scope.
* It detects `sid=<value>; Domain=.example.com; Path=/` set by `admin.eu.example.com` as broad domain scope.
* It marks host-only sensitive cookies as rejected or emits no vulnerability finding.
* It handles invalid public-suffix domains without crashing.
* It respects configured `allowed_cookie_domain_patterns`.
* It redacts cookie values in logs and findings.
* It links each finding to at least one `Evidence` record.

Negative assertions:

* It must not flag non-sensitive analytics, consent, locale, theme, or preference cookies by default.
* It must not hard-code hostname-to-cookie expectations.
* It must not attempt login.
* It must not call logout.
* It must not send mutating HTTP methods.
* It must not inject cookies.
* It must not attempt cookie tossing.
* It must not brute-force or visit sibling subdomains.
* It must not perform subdomain takeover checks.
* It must not store raw cookie values in findings.
* It must not send cookie evidence to an LLM.
* It must not fail the whole scan when no cookies are set.

## Test fixtures

Use the synthetic fixture slug: `session-cookie-attributes`.

Required fixture routes:

| Route | Host context | Behavior | Expected result |
| ----- | ------------ | -------- | --------------- |
| `/domain/parent-scope` | `app.example.test` | Sets `sid=vulnerable; Domain=example.test; Path=/; Secure; HttpOnly` | `confirmed`, `high` |
| `/domain/deep-parent-scope` | `admin.eu.example.test` | Sets `sid=vulnerable; Domain=.example.test; Path=/; Secure; HttpOnly` | `confirmed`, `high` |
| `/domain/host-only` | `app.example.test` | Sets `sid=safe; Path=/; Secure; HttpOnly` | `rejected`, `high` or no finding |
| `/domain/exact-host-domain` | `app.example.test` | Sets `sid=maybe; Domain=app.example.test; Path=/; Secure; HttpOnly` | `candidate`, `low` |
| `/domain/apex-domain` | `example.test` | Sets `sid=maybe; Domain=example.test; Path=/; Secure; HttpOnly` | `candidate`, `medium` |
| `/domain/public-suffix-invalid` | `app.example.test` | Sets `sid=bad; Domain=test; Path=/; Secure; HttpOnly` | `rejected`, `high` or no finding |
| `/domain/allowlisted-sso` | `app.example.test` | Sets allowlisted `sso_state=value; Domain=example.test; Path=/; Secure; HttpOnly` | no vulnerability finding |
| `/domain/preference-cookie` | `app.example.test` | Sets `theme=dark; Domain=example.test; Path=/` | no vulnerability finding |

Compatibility fixtures:

* `juice-shop` and `dvwa` may be used for exploratory validation of real cookie scopes.
* Do not make acceptance depend on live fixture cookie settings that may vary by reverse proxy, host header, or container version.

## Acceptance criteria

The implementation is acceptable when:

* The check is idempotent and read-only.
* The default unauthenticated scan sends no more than `max_public_requests`.
* The authenticated scan uses only an existing authenticated context and sends no more than `max_authenticated_requests`.
* It completes within the Phase 3 request budget.
* It handles no-cookie responses without errors.
* It handles duplicate cookie names on different paths or domains.
* It handles malformed `Set-Cookie` headers without crashing.
* It handles redirects and records which response set the cookie.
* It uses a public-suffix-aware parser for domain comparisons.
* It handles internationalized domains according to the project hostname normalization helper.
* It redacts cookie values consistently in logs, evidence excerpts, and findings.
* It produces deterministic statuses and confidence values.
* It stores findings with at least one evidence ID.
* It defines only `BroadDomainScopeSignature` and `BroadDomainScopeFinding` as stub-specific types.
* Unit tests cover domain normalization, public-suffix rejection, host-only cookies, parent-domain scope, apex-domain scope, exact-host `Domain`, allowlist behavior, redaction, duplicate cookie handling, stale handling, and negative assertions.
* Fixture tests cover parent scope, deep parent scope, host-only scope, exact-host domain, apex-domain scope, invalid public suffix, allowlisted SSO cookies, and preference cookies.
* AI is not called.
