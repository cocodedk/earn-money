---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 1
spec: 8
slug: exposed-admin-panels
status: done        # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 1.8 Exposed admin panels

> Phase 1 — Information gathering · Category: Content discovery

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

Detect admin, management, console, dashboard, and control-panel routes that are reachable from the scanned target. A runner cares because these paths often define the next safe scan boundary: exposed login panels, unauthenticated admin pages, default consoles, and publicly reachable management interfaces all change risk and guide later checks.

## Inputs

The runner receives a shared `ScanTarget` and uses its `base_url` as the scan root.

Required input:

* `ScanTarget`

  * Use `base_url`, `host`, and `id`.
  * Do not redefine `ScanTarget`.

Optional input:

* `credentials`

  * Optional.
  * This spec does not use credentials in the MVP.
  * If credentials are present, this detector must still run in unauthenticated mode unless the caller explicitly enables authenticated scanning in a later spec.
* `config`

  * `path_wordlist`: ordered list of candidate admin paths.
  * `max_paths`: upper bound for candidate paths checked per target.
  * `timeout_ms`: per-request timeout.
  * `max_response_bytes`: maximum body bytes stored as evidence.
  * `follow_redirects`: default `false`.
  * `same_origin_redirects_only`: default `true`.
  * `allowed_statuses`: default `[200, 301, 302, 303, 307, 308, 401, 403]`.
  * `baseline_paths`: random unlikely paths used for soft-404 comparison.
  * `user_agent`: scanner user agent from shared runner config.
  * `rate_limit`: shared per-target request pacing.
  * `respect_robots_txt`: default `false` for security scanning; if enabled globally, obey shared runner policy.

Default candidate paths:

```text
/admin
/admin/
/administrator
/administrator/
/admin/login
/admin/login/
/admin.php
/admincp
/admincp/
/backend
/backend/
/console
/console/
/controlpanel
/controlpanel/
/cpanel
/dashboard
/dashboard/
/manage
/manage/
/management
/management/
/manager
/manager/
/moderator
/moderator/
/panel
/panel/
/portal/admin
/portal/admin/
/siteadmin
/siteadmin/
/staff
/staff/
/superadmin
/superadmin/
/system
/system/
/wp-admin/
/wp-login.php
```

The implementation may allow project-level extensions, but the default list must stay small for phase 1.

## Detection logic

Detection is deterministic and uses only HTTP evidence.

### Request plan

1. Normalize `base_url`.
2. Fetch a small baseline set:

   * `GET /`
   * `GET /<random-high-entropy-path>`
   * `GET /<another-random-high-entropy-path>`
3. For each candidate path:

   * Send `GET`.
   * Do not send POST, PUT, PATCH, DELETE, OPTIONS, TRACE, or CONNECT.
   * Do not submit forms.
   * Do not click buttons.
   * Do not follow cross-origin redirects.
   * If `follow_redirects=true`, follow only same-origin redirects and cap redirect depth at 3.
4. Store one `Evidence` item per meaningful response.
5. Compare each response against baseline responses before creating a finding.

### Candidate response signals

A candidate path is interesting when at least one of these deterministic signals is present:

* HTTP status is `200`, `401`, or `403`.
* HTTP status is a redirect to a same-origin path containing admin-like terms.
* Response title or body contains admin-panel terms.
* Response contains login-form markers on an admin-like path.
* Response contains known management-console markers.
* Response headers indicate a protected admin route.
* Response differs strongly from the soft-404 baseline.

Admin-like path terms:

```text
admin
administrator
backend
console
control panel
dashboard
manage
management
manager
moderator
panel
siteadmin
staff
superadmin
system
```

Login-form markers:

```text
type="password"
name="password"
id="password"
autocomplete="current-password"
login
sign in
username
email
csrf
```

Management-console markers:

```text
admin dashboard
admin panel
administrator login
control panel
management console
site administration
server status
system dashboard
web console
wp-admin
wordpress
phpmyadmin
pgadmin
grafana
kibana
jenkins
sonarqube
prometheus
traefik
portainer
rabbitmq management
elasticsearch
swagger ui
openapi
```

Header markers:

* `WWW-Authenticate` exists on an admin-like path.
* `Location` header points to an admin-like same-origin path.
* `X-Frame-Options`, `Content-Security-Policy`, or security headers alone must not create a finding. They may support evidence only after a path/content match exists.

### Soft-404 and false-positive handling

A path must not be reported only because it returned `200`.

Compare each candidate response with baseline random-path responses:

* If status, body length, title, and body hash are close to random-path responses, mark as `rejected`.
* If the body contains generic not-found text, mark as `rejected`.
* If the app shell returns the same SPA page for every unknown route, require stronger content evidence before reporting.

Generic not-found markers:

```text
404
not found
page not found
route not found
cannot get
no such page
```

SPA fallback handling:

* If `/admin` returns the same shell as random paths, do not confirm it.
* If the shell contains route-specific admin text, create a `candidate`.
* If route-specific admin text appears only after JavaScript execution, this detector must not infer it unless the shared runner already has a deterministic browser-rendering capability. If not available, leave browser-rendered checks to a later spec.

### Confidence rules

Use these rules:

* `high`

  * Admin-like path exists, and response has status `200`, `401`, or `403`, and body/title/header evidence clearly indicates an admin, login, dashboard, management, or console interface.
  * Or same-origin redirect leads to a clearly named admin/login route and final response contains login/admin markers.
* `medium`

  * Admin-like path exists and returns `401` or `403` with `WWW-Authenticate`, but body is sparse.
  * Or path and title/body suggest admin access, but the page may be a generic login reused across the site.
* `low`

  * Path is admin-like and differs from soft-404 baseline, but content evidence is weak.
  * Or only redirect evidence exists without a final readable body.

Do not create a `confirmed` finding from `low` confidence.

### Status rules

* `candidate`

  * The route has at least weak deterministic evidence but not enough to prove exposure.
* `confirmed`

  * The route is reachable and has medium or high confidence.
  * `401` and `403` can be confirmed as exposed admin surfaces because the route itself is reachable.
* `rejected`

  * The response matches soft-404, generic SPA fallback, generic not-found page, cross-origin redirect, or unrelated login.
* `stale`

  * Previously detected route no longer reproduces after a fresh run.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them.

Define only the stub-specific types below.

### `ExposedAdminPanelSignature`

One checked route and the deterministic signals observed for it.

```json
{
  "id": "uuid",
  "scan_target_id": "uuid",
  "path": "/admin",
  "url": "https://example.test/admin",
  "method": "GET",
  "status_code": 200,
  "redirect_chain": [
    {
      "status_code": 302,
      "location": "/admin/login",
      "same_origin": true
    }
  ],
  "final_url": "https://example.test/admin/login",
  "content_type": "text/html",
  "title": "Admin login",
  "body_sha256": "hex",
  "body_length": 4217,
  "matched_path_terms": ["admin"],
  "matched_body_terms": ["admin login", "type=\"password\""],
  "matched_header_terms": [],
  "soft_404_like": false,
  "spa_fallback_like": false,
  "evidence_ids": ["uuid"],
  "created_at": "ISO-8601"
}
```

Field rules:

* `path` is the candidate path requested.
* `url` is the requested URL.
* `final_url` is the last same-origin URL reached after allowed redirects.
* `redirect_chain` is empty when redirects are not followed or absent.
* `matched_*_terms` contain exact deterministic matches.
* `soft_404_like` is true when the response resembles random-path baselines.
* `spa_fallback_like` is true when the response resembles a generic SPA shell.
* `evidence_ids` references shared `Evidence` rows.

### `ExposedAdminPanelFinding`

One reportable exposed admin surface.

```json
{
  "id": "uuid",
  "scan_target_id": "uuid",
  "signature_id": "uuid",
  "finding_type": "exposed_admin_panel",
  "path": "/admin",
  "url": "https://example.test/admin",
  "final_url": "https://example.test/admin/login",
  "status": "candidate | confirmed | rejected | stale",
  "confidence": "low | medium | high",
  "exposure_kind": "admin_login | admin_dashboard | management_console | protected_admin_route | unknown_admin_surface",
  "access_state": "public_200 | auth_required_401 | forbidden_403 | redirected_same_origin | unknown",
  "summary": "Reachable admin login panel at /admin.",
  "evidence_ids": ["uuid"],
  "first_seen_at": "ISO-8601",
  "last_seen_at": "ISO-8601",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

Field rules:

* `finding_type` must be exactly `exposed_admin_panel`.
* `status` must be one of `candidate`, `confirmed`, `rejected`, `stale`.
* `confidence` must be one of `low`, `medium`, `high`.
* `exposure_kind` must be derived from path, status, headers, title, and body markers.
* `access_state` must be derived from HTTP status and redirect behavior.
* `summary` must be factual and evidence-based.
* Do not persist guessed product names unless detected from evidence.
* Do not persist credentials, cookies, full response bodies, or form values in the finding.

### Evidence requirements

Each reported finding must reference at least one shared `Evidence` item.

Evidence should include:

* request method
* requested URL
* status code
* response headers after redaction
* response body excerpt after truncation
* body hash
* timestamp
* redirect information, if any

Redact before persistence:

* cookies
* authorization headers
* session IDs
* CSRF tokens
* access tokens
* API keys
* passwords
* email addresses where not needed for proof

## Safety

This detector is read-only.

Allowed:

* `GET /`
* `GET /candidate-path`
* Same-origin redirect following when enabled and capped
* Response header inspection
* Response body inspection
* Deterministic string and hash comparison

Not allowed:

* POSTing login forms
* Guessing credentials
* Password spraying
* Brute forcing paths beyond the configured small wordlist
* Mutating admin settings
* Creating, deleting, or changing records
* Uploading files
* Calling admin APIs
* Sending payloads intended to exploit a panel
* Following cross-origin redirects
* Running JavaScript unless a later shared browser-rendering capability explicitly allows deterministic rendering

Payload restrictions:

* No attack payloads.
* No form submissions.
* No query parameters intended to bypass auth.
* Candidate URLs must be simple path probes.

PII handling:

* Do not store full admin pages when they contain user lists, emails, logs, or personal data.
* Store a short excerpt around matched terms.
* Store hashes and metadata for audit.
* Redact sensitive headers and body values before persistence.

AI involvement:

* `None`.

Deterministic gap:

* If a panel is visible only after JavaScript execution and the shared runner has no deterministic browser-rendering capability, this detector must not ask an AI to infer it. Leave the route as `candidate` or `rejected` based on HTTP evidence only.

## Pass/fail check

A run passes when all assertions below hold.

### Positive assertions

* Given a target with `/admin` returning `200` and body containing `Admin login` plus `type="password"`, the detector creates one `ExposedAdminPanelFinding`.
* The finding has:

  * `finding_type = "exposed_admin_panel"`
  * `status = "confirmed"`
  * `confidence = "high"`
  * `exposure_kind = "admin_login"`
  * `access_state = "public_200"`
  * at least one `evidence_id`
* Given `/admin` returning `401` with `WWW-Authenticate`, the detector creates a finding with:

  * `status = "confirmed"`
  * `confidence = "medium"` or `high`
  * `access_state = "auth_required_401"`
* Given `/admin` returning `403` with admin-like body or path evidence, the detector creates a finding with:

  * `status = "confirmed"`
  * `access_state = "forbidden_403"`
* Given `/admin` redirecting to same-origin `/admin/login`, and `/admin/login` contains login markers, the detector reports the final same-origin admin login.
* Given a previous confirmed finding that no longer reproduces, the detector marks it `stale`.

### Negative assertions

* Must not report a finding only because a path returns `200`.
* Must not report `/admin` when it returns the same generic SPA shell as random baseline paths.
* Must not report `/admin` when the body is a generic 404 page.
* Must not report cross-origin redirects as exposed admin panels.
* Must not submit login forms.
* Must not send POST, PUT, PATCH, DELETE, OPTIONS, TRACE, or CONNECT.
* Must not use credentials unless a later authenticated spec explicitly enables it.
* Must not hard-code hostname-specific expected panels.
* Must not infer product names from hostname.
* Must not store cookies, authorization headers, CSRF tokens, passwords, or full sensitive bodies.
* Must not call an AI model.
* Must not mark low-confidence routes as `confirmed`.

### Idempotence assertions

* Running the detector twice against the same unchanged target must not create duplicate findings.
* The existing finding should be updated with `last_seen_at` and latest evidence.
* Stable fields such as `scan_target_id`, `finding_type`, `path`, and `url` should remain consistent.

## Test fixtures

Use one fixture with deterministic routes.

Recommended new fixture slug:

* `admin-panel-demo`

Fixture behavior:

* `GET /`

  * Returns normal home page.
* `GET /admin`

  * Returns `200`.
  * Body includes `<title>Admin login</title>`, `Admin login`, and `<input type="password" name="password">`.
* `GET /admin-basic`

  * Returns `401`.
  * Header includes `WWW-Authenticate: Basic realm="Admin"`.
* `GET /admin-forbidden`

  * Returns `403`.
  * Body includes `Admin area`.
* `GET /admin-redirect`

  * Returns `302`.
  * Header `Location: /admin/login`.
* `GET /admin/login`

  * Returns `200`.
  * Body includes login markers.
* `GET /fake-admin`

  * Returns the same generic 404 page as random paths.
* `GET /spa-admin`

  * Returns the same SPA shell as unknown routes.
* `GET /external-admin`

  * Returns `302`.
  * Header `Location: https://admin.example.invalid/`.
* `GET /anything-random`

  * Returns generic 404 or generic SPA fallback, depending on route group.

Optional existing fixtures:

* `juice-shop`

  * May be used only for smoke testing route discovery behavior.
  * Do not hard-code Juice Shop expected routes.
  * Do not require Juice Shop-specific findings for acceptance unless the fixture is pinned and stable.
* `dvwa`

  * Useful for generic login-route smoke testing, but not required for this spec.
* `webgoat`

  * Useful for auth-boundary smoke testing, but not required for this spec.

## Acceptance criteria

The implementation is acceptable when:

* It uses shared `ScanTarget` and `Evidence`.
* It defines only `ExposedAdminPanelSignature` and `ExposedAdminPanelFinding` as stub-specific types.
* It performs deterministic, read-only detection.
* It never uses AI.
* It sends only safe `GET` requests.
* It does not submit forms or credentials.
* It handles redirects according to config and rejects cross-origin redirects.
* It compares candidate responses against random-path baselines.
* It rejects soft-404 and generic SPA fallback responses.
* It records exact matched terms and evidence IDs.
* It assigns only `low`, `medium`, or `high` confidence.
* It assigns only `candidate`, `confirmed`, `rejected`, or `stale` status.
* It avoids duplicate findings across repeated runs.
* It redacts sensitive headers and body values before persistence.
* It completes within the configured request and path budget.
* It handles TLS errors, timeouts, connection failures, and invalid responses gracefully.
* It does not retry flaky paths endlessly.
* It uses bounded retries only for transient network errors if shared runner policy allows retries.
* It produces clear logs for checked path count, rejected soft-404 count, finding count, and error count.
* It follows the coding-agent rules in `../00-shared-schema.md`.
* It remains paste-compatible with the cookbook format.

