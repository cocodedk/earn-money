---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 1
spec: 18
slug: framework-debug-pages
status: done        # pending | in-progress | blocked | done — absorbed into stub 1.10 (see closure note below)
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 1.18 Framework debug pages

> Phase 1 — Information gathering · Category: Error disclosure

> **Closure (2026-05-20):** This spec's coverage is delivered by stub **1.10 (debug-pages)**, not by a separate `apps/stubs/framework_debug_pages/` package. PR #29 extended stub 1.10's `DebugPageKind` set, signatures, and path hints to cover every framework-debug-page family this spec calls for (laravel_debugbar / aspnet_tracing / elmah / yii_debug / jboss_wildfly_console — with WildFly + JBoss vendor split — plus an `apache_server_info` body signature). No new stub will be built for 1.18. See [`./10-debug-pages.md`](./10-debug-pages.md) for the active contract and the merge commit `c4087d9` (PR #29) for the absorption diff.

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

Detect exposed framework debug pages that reveal application internals through built-in development or error views. A runner cares because these pages often disclose framework names, versions, routes, environment variables, file paths, stack frames, loaded modules, request metadata, secrets, database settings, or enabled debug flags. This check is read-only and records only evidence that can be observed from HTTP responses inside the allowed scan scope.

## Inputs

The runner receives a shared `ScanTarget` and produces zero or more framework debug page findings.

Required inputs:

* `ScanTarget`

  * Use the shared type from `../00-shared-schema.md`.
  * The runner must use `base_url` as the root of the allowed scope.
  * The runner must not infer expected framework from hostname, fixture name, page title, or operator notes.

Optional inputs:

* `credentials`

  * Optional authenticated session material supplied by the scan orchestrator.
  * The runner must not create accounts, brute force credentials, guess sessions, or submit login forms unless another approved authenticated-scanning component already produced a valid session.
* `candidate_paths`

  * Extra paths supplied by configuration or earlier discovery steps.
  * These are appended to the built-in passive debug path list.
* `max_requests`

  * Default: `40`.
  * Hard cap for this check per target.
* `timeout_seconds`

  * Default: `10`.
* `max_response_bytes`

  * Default: `512000`.
  * Responses larger than this must be truncated for analysis and evidence storage.
* `follow_redirects`

  * Default: `false`.
  * If enabled by global scanner policy, follow only same-origin redirects.
* `include_404_body_analysis`

  * Default: `false`.
  * Avoid treating branded 404 pages as debug pages unless strong debug markers are present.
* `allowed_methods`

  * Default: `["GET", "HEAD"]`.
  * `POST`, `PUT`, `PATCH`, and `DELETE` are not allowed for this check.
* `user_agent`

  * Scanner-controlled value from shared configuration.
* `rate_limit`

  * Optional per-target delay or token bucket controlled by the scan orchestrator.

Built-in candidate paths should be small and framework-focused. Initial list:

* `/debug`
* `/debug/`
* `/debug/default/view`
* `/debug/default/toolbar`
* `/debug/default/download`
* `/_debug_toolbar/`
* `/_profiler/`
* `/_profiler/phpinfo`
* `/_profiler/latest`
* `/__debugbar`
* `/__debugbar/open`
* `/__debugbar/assets/stylesheets`
* `/__debugbar/assets/javascript`
* `/telescope`
* `/telescope/requests`
* `/horizon`
* `/rails/info/routes`
* `/rails/info/properties`
* `/elmah.axd`
* `/trace.axd`
* `/actuator`
* `/actuator/env`
* `/actuator/beans`
* `/actuator/mappings`
* `/actuator/heapdump`
* `/actuator/threaddump`
* `/web-console/`
* `/console`
* `/werkzeug/console`
* `/django-debug-toolbar/`
* `/__debugger__`
* `/server-status`
* `/server-info`

The list is not proof by itself. A finding must be based on response evidence.

## Detection logic

Detection is deterministic and based on HTTP response evidence.

### Request plan

1. Normalize `ScanTarget.base_url`.
2. Build candidate URLs from:

   * built-in framework debug paths,
   * caller-supplied `candidate_paths`,
   * paths discovered by previous passive checks, such as source maps, public JavaScript bundles, robots.txt, sitemap.xml, stack traces, or verbose API errors.
3. Deduplicate URLs by normalized scheme, host, port, and path.
4. Stay within the target origin unless the scan policy explicitly allows additional in-scope origins.
5. Send `HEAD` first only when the scanner already uses that pattern. Do not rely on `HEAD` alone for detection because many debug pages return weak headers.
6. Send `GET` for candidate paths until `max_requests` is reached.
7. Store one `Evidence` record per meaningful response.
8. Analyze response status, headers, and body using the signatures below.
9. Mark a finding as `confirmed` only when a debug page is directly exposed and the response contains enough framework-specific or debug-specific markers.
10. Mark weak matches as `candidate`.
11. Mark non-matches as no finding. Do not persist rejected findings unless the project keeps negative scan records.

### Status handling

A response can be analyzed when status is one of:

* `200`
* `203`
* `206`
* `301`, `302`, `303`, `307`, `308` when the `Location` header is same-origin and points to another debug-looking path
* `401` or `403` when the body, headers, or realm clearly identify a protected debug console
* `500` only when the body is a framework debug page, not just a normal error page

Do not confirm a finding from status alone.

### Debug page families

The runner should support deterministic signatures for at least these families:

| Family                 | Example markers                                                                       | Minimum confirmation evidence                                                |
| ---------------------- | ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Django Debug Toolbar   | `djDebug`, `__debug__`, `django-debug-toolbar`, `SQLPanel`, `HistoryPanel`            | `200` body with toolbar marker and Django/debug panel marker                 |
| Symfony Profiler       | `_profiler`, `sf-toolbar`, `Symfony Profiler`, `X-Debug-Token`, `X-Debug-Token-Link`  | profiler path or header plus Symfony profiler marker                         |
| Laravel Debugbar       | `Laravel Debugbar`, `phpdebugbar`, `__debugbar`, `Debugbar`                           | debugbar route/body plus Laravel or phpdebugbar marker                       |
| Laravel Telescope      | `Laravel Telescope`, `/telescope/requests`, `telescopeEntries`                        | Telescope route body or title plus Laravel/Telescope marker                  |
| Laravel Horizon        | `Laravel Horizon`, `horizon`, `Jobs Per Minute`, `Wait Time`                          | Horizon route body plus Horizon-specific UI marker                           |
| Rails info routes      | `Routes`, `rails/info/routes`, `Action Controller`, `Rails.application.routes`        | `/rails/info/routes` response plus routes-specific marker                    |
| ASP.NET tracing        | `trace.axd`, `Application Trace`, `Trace Information`, `Request Details`              | trace endpoint body plus ASP.NET tracing marker                              |
| ELMAH                  | `elmah.axd`, `Error Log for`, `ELMAH`, `ErrorLogPageFactory`                          | ELMAH endpoint body plus ELMAH marker                                        |
| Spring Boot Actuator   | `/actuator`, `_links`, `health`, `env`, `beans`, `mappings`, `heapdump`, `threaddump` | actuator path plus valid actuator-shaped JSON or sensitive actuator endpoint |
| Werkzeug debugger      | `Werkzeug`, `Console Locked`, `Traceback`, `__debugger__`, `PIN`                      | Werkzeug debugger marker plus traceback or console marker                    |
| Flask debug console    | `werkzeug`, `flask`, `Debugging middleware caught exception`                          | Flask/Werkzeug body marker plus debugger marker                              |
| Yii debug toolbar      | `yii-debug-toolbar`, `Yii Debugger`, `debug/default/view`                             | Yii debug route or toolbar marker plus Yii marker                            |
| Web server status/info | `server-status`, `Apache Server Status`, `server-info`, `mod_status`, `mod_info`      | server status/info path plus Apache status/info marker                       |
| JBoss/WildFly console  | `HAL Management Console`, `WildFly`, `JBoss`, `web-console`                           | console path plus management-console marker                                  |

### Signature scoring

Each response is evaluated against a set of signatures. A signature match returns:

* matched framework or component family,
* matched markers,
* sensitive fields observed,
* confidence,
* reason for confidence,
* evidence IDs.

Suggested deterministic scoring:

* `high`

  * A known debug path responds with `200`, `401`, or `403`, and
  * body/header contains at least two family-specific markers, or
  * one family-specific marker plus sensitive debug data such as env vars, stack frames, routes, SQL queries, heap/thread dump, config keys, or request details.
* `medium`

  * A known debug path responds and contains one strong family marker, or
  * an unknown path contains multiple debug markers and sensitive debug data.
* `low`

  * A response contains weak debug-looking terms but lacks framework-specific evidence.
  * Low confidence findings should remain `candidate`.

### Strong marker examples

Use case-insensitive matching where safe. Prefer exact tokens, HTML IDs/classes, headers, and structured JSON keys over broad words.

Strong markers include:

* Headers:

  * `X-Debug-Token`
  * `X-Debug-Token-Link`
  * `X-Runtime` only as weak supporting evidence, never alone
  * `X-Powered-By` only as supporting evidence, never alone
* HTML IDs/classes:

  * `id="djDebug"`
  * `class="sf-toolbar"`
  * `id="sfMiniToolbar"`
  * `phpdebugbar`
  * `yii-debug-toolbar`
* Paths in links or scripts:

  * `/_profiler/`
  * `/__debugbar/`
  * `/debug/default/`
  * `/rails/info/routes`
  * `/elmah.axd`
  * `/trace.axd`
  * `/actuator/`
* JSON actuator keys:

  * `_links`
  * `self.href`
  * `health.href`
  * `env.href`
  * `beans.href`
  * `mappings.href`
  * `heapdump.href`
  * `threaddump.href`

### Sensitive debug data indicators

Sensitive debug data should raise confidence when paired with a debug page marker:

* environment variable names or values,
* framework version,
* package/module versions,
* file paths,
* stack frames,
* route tables,
* controller/action names,
* database connection strings,
* SQL query logs,
* request headers,
* cookies,
* session IDs,
* server variables,
* application settings,
* bean mappings,
* thread dumps,
* heap dump endpoint exposure,
* profiler tokens,
* debug toolbar panels.

### False positive controls

The runner must avoid these false positives:

* Generic pages that contain the word `debug` in marketing copy, docs, blog posts, or JavaScript variable names.
* Normal framework error pages without debug mode enabled.
* API responses that include a field named `debug` but no debug UI, debug endpoint, or sensitive data.
* Auth login pages for admin areas unless the page clearly identifies a framework debug console.
* Branded 404 pages for debug paths.
* Redirects to `/login`, `/signin`, `/admin`, `/account`, or an identity provider unless the source path and redirect chain identify a protected debug page.
* `X-Powered-By` alone.
* Server banners alone.
* Stack traces already handled by spec `1.16 Stack traces`, unless the same response also exposes a framework debug console or debug toolbar.
* Verbose API errors already handled by spec `1.17 Verbose API errors`, unless the response is a known debug endpoint.

### Finding status

* `confirmed`

  * Direct evidence shows an exposed framework debug page or protected debug console endpoint.
* `candidate`

  * Evidence suggests a debug page, but the response lacks enough markers for confirmation.
* `rejected`

  * Optional only if the project stores negative results. Use when a candidate path was checked and clearly not a debug page.
* `stale`

  * A previously confirmed finding no longer reproduces on the latest scan.

### AI involvement

None. All matching, scoring, and classification must be deterministic.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them.

Define only these stub-specific types:

```typescript
type FrameworkDebugPageSignature = {
  id: string;
  family:
    | "django_debug_toolbar"
    | "symfony_profiler"
    | "laravel_debugbar"
    | "laravel_telescope"
    | "laravel_horizon"
    | "rails_info"
    | "aspnet_trace"
    | "elmah"
    | "spring_boot_actuator"
    | "werkzeug_debugger"
    | "flask_debugger"
    | "yii_debugger"
    | "apache_status_info"
    | "jboss_wildfly_console"
    | "other";

  candidate_paths: string[];
  status_allowlist: number[];

  header_markers: string[];
  body_markers: string[];
  path_markers: string[];
  json_markers: string[];

  sensitive_data_markers: string[];

  min_markers_for_candidate: number;
  min_markers_for_confirmed: number;

  confidence_hint: "low" | "medium" | "high";
  notes?: string;
};

type FrameworkDebugPageFinding = {
  id: string;
  scan_target_id: ScanTarget["id"];

  url: string;
  method: "GET" | "HEAD";
  status_code: number;

  family: FrameworkDebugPageSignature["family"];
  signature_id: FrameworkDebugPageSignature["id"];

  title: string;
  summary: string;

  matched_path: string;
  matched_headers: string[];
  matched_body_markers: string[];
  matched_json_markers: string[];
  sensitive_data_observed: string[];

  evidence_ids: Evidence["id"][];

  confidence: "low" | "medium" | "high";
  status: "candidate" | "confirmed" | "rejected" | "stale";

  first_seen_at: string;
  last_seen_at: string;

  response_hash: string;
  content_type?: string;
  response_size_bytes?: number;
  body_truncated: boolean;

  remediation: {
    summary: string;
    steps: string[];
  };

  safety: {
    read_only: true;
    mutating_requests_sent: false;
    authentication_used: boolean;
    pii_or_secret_risk: "none" | "possible" | "observed";
    redaction_applied: boolean;
  };

  references: {
    related_specs: string[];
  };
};
```

Persistence rules:

* Store one finding per unique `(scan_target_id, url, family, signature_id)`.
* Update `last_seen_at` when the finding reproduces.
* Keep `first_seen_at` from the first confirmed or candidate observation.
* Store `response_hash` so stale findings can be detected.
* Store raw response body only through the shared `Evidence` mechanism.
* Evidence must be redacted or truncated according to shared scanner policy.
* Do not store full cookies, authorization headers, session IDs, access tokens, CSRF tokens, database passwords, private keys, or raw heap dumps in the finding object.
* If sensitive data is observed, record only the type in `sensitive_data_observed`, not the secret value.
* Use `references.related_specs` to point to overlapping checks such as:

  * `1.16 Stack traces`
  * `1.17 Verbose API errors`
  * `1.15 Public JavaScript bundles`
  * `1.14 Source maps`

Suggested remediation text:

* Disable framework debug mode in non-development environments.
* Block debug routes at the application router, reverse proxy, or ingress layer.
* Restrict profiler, actuator, trace, and status endpoints to trusted networks or authenticated admin users.
* Remove debug toolbars and development middleware from production builds.
* Review exposed evidence for leaked secrets and rotate any affected credentials.
* Add a regression test or deployment gate that fails when debug endpoints are reachable from outside the intended network.

## Safety

This check is read-only.

Allowed behavior:

* `GET` and optional `HEAD` requests only.
* Same-origin redirects only when redirect following is enabled by scanner policy.
* Use existing authenticated session only when the scan orchestrator provides it and the target scope allows authenticated scanning.
* Truncate large responses.
* Redact obvious secrets before logging or displaying evidence.
* Record only minimal evidence needed to prove the finding.

Forbidden behavior:

* No `POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS` with side effects, or WebSocket interaction.
* No form submission.
* No login attempts.
* No credential guessing.
* No use of discovered tokens or credentials.
* No interaction with debug consoles.
* No execution of commands through consoles such as Werkzeug, Flask, Rails console, Django shell, JBoss console, or similar.
* No heap dump download unless a separate explicit policy allows large sensitive artifact retrieval. For this check, detecting that `/actuator/heapdump` is exposed is enough.
* No brute force of profiler tokens.
* No recursive crawling of debug interfaces.
* No requests outside target scope.
* No hostname-to-technology assumptions.

Payload restrictions:

* This check sends no exploit payloads.
* Candidate paths are static route probes only.
* Query strings must be empty unless the signature requires a harmless known static asset path.
* Do not append debug-enabling parameters such as `?debug=true`, `?XDEBUG_SESSION_START=`, `?profiler=1`, or similar in the first version.

PII and secret handling:

* Treat debug pages as likely sensitive.
* Do not include full environment values, cookies, headers, SQL rows, session values, stack locals, heap dump bytes, or thread dump bodies in user-facing summaries.
* Evidence snippets should be short and redacted.
* The finding may say `DATABASE_URL observed` or `session cookie observed`, but must not store or display the actual value.

AI involvement:

* `None`.
* There is no deterministic gap that requires AI for this version.
* If a future implementation adds AI for explanation text, it must only receive redacted finding summaries and evidence IDs, not raw debug page bodies.

## Pass/fail check

A runner passes this spec when all assertions below are true.

Positive assertions:

* Given a target exposing Django Debug Toolbar at a debug path, the runner creates a `FrameworkDebugPageFinding` with:

  * `family = "django_debug_toolbar"`,
  * `status = "confirmed"`,
  * `confidence = "high"` or `"medium"`,
  * at least one `Evidence` ID,
  * matched toolbar markers recorded.
* Given a target exposing Symfony profiler headers or toolbar, the runner records the profiler token/header/body markers and confirms the finding when enough markers are present.
* Given a target exposing Laravel Debugbar or Telescope, the runner identifies the correct family from response evidence.
* Given a target exposing `/rails/info/routes`, the runner confirms only when Rails route information is present.
* Given a target exposing Spring Boot Actuator JSON, the runner confirms only when actuator-shaped JSON or sensitive actuator endpoint evidence is present.
* Given a protected debug console returning `401` or `403`, the runner creates at most a `candidate` or `confirmed` finding based on explicit debug markers, not status alone.
* Every confirmed finding includes:

  * target ID,
  * URL,
  * method,
  * status code,
  * family,
  * signature ID,
  * matched markers,
  * evidence IDs,
  * confidence,
  * status,
  * remediation.
* Re-running the check against the same exposed page updates the existing finding instead of creating duplicates.
* If a previously confirmed debug page no longer reproduces, the runner can mark it `stale` according to shared stale-finding policy.

Negative assertions:

* The runner must not confirm a finding from `X-Powered-By` alone.
* The runner must not confirm a finding from a generic `debug` word in a normal page.
* The runner must not confirm a branded 404 page as a debug page.
* The runner must not confirm a login page as a debug page unless the page clearly identifies a framework debug console.
* The runner must not send `POST`, `PUT`, `PATCH`, or `DELETE`.
* The runner must not submit forms.
* The runner must not execute commands in any debug console.
* The runner must not brute force profiler tokens, PINs, paths, or credentials.
* The runner must not download full heap dumps, logs, databases, or archives.
* The runner must not store raw secrets in the finding object.
* The runner must not hard-code fixture hostname to expected technology.
* The runner must not use AI classification.
* The runner must not follow redirects to a different origin unless global scope policy allows it.
* The runner must not exceed `max_requests`.
* The runner must not keep retrying flaky endpoints beyond the shared retry budget.

Example deterministic unit checks:

* `200 /_profiler/` with `sf-toolbar` and `X-Debug-Token` means confirmed Symfony profiler.
* `200 /_profiler/` with a custom 404 page mentioning `profile your app` means no finding.
* `200 /actuator` with HAL `_links` to `health`, `env`, and `beans` means confirmed Spring Boot Actuator.
* `403 /actuator/env` with `application/json` and actuator error shape means candidate or confirmed depending on marker strength.
* `200 /debug` with a blog article titled `How to debug JavaScript` means no finding.
* `200 /server-status` with `Apache Server Status for` means confirmed Apache status/info.
* `302 /_profiler/` to `/login` with no Symfony marker means no confirmed finding.

## Test fixtures

Use one or more controlled fixtures. Do not depend on public internet targets.

Recommended fixture plan:

### `framework-debug-pages`

Create a small dedicated fixture with several routes. This is the preferred fixture because it avoids changing DVWA, Juice Shop, or WebGoat behavior.

Routes:

* `/django-toolbar`

  * Returns `200 text/html`.
  * Contains `id="djDebug"`, `django-debug-toolbar`, `SQLPanel`.
* `/_profiler/`

  * Returns `200 text/html`.
  * Contains `sf-toolbar`, `_profiler`, `Symfony Profiler`.
  * Adds `X-Debug-Token` and `X-Debug-Token-Link`.
* `/__debugbar`

  * Returns `200 text/html`.
  * Contains `Laravel Debugbar`, `phpdebugbar`, `__debugbar`.
* `/telescope`

  * Returns `200 text/html`.
  * Contains `Laravel Telescope`, `/telescope/requests`.
* `/rails/info/routes`

  * Returns `200 text/html`.
  * Contains `Routes`, `rails/info/routes`, `Rails.application.routes`.
* `/actuator`

  * Returns `200 application/json`.
  * Contains `_links` with `health`, `env`, `beans`, `mappings`.
* `/actuator/env`

  * Returns `200 application/json`.
  * Contains realistic but fake keys.
  * Values must be dummy strings, never real secrets.
* `/elmah.axd`

  * Returns `200 text/html`.
  * Contains `Error Log for`, `ELMAH`.
* `/trace.axd`

  * Returns `200 text/html`.
  * Contains `Application Trace`, `Trace Information`, `Request Details`.
* `/werkzeug/console`

  * Returns `200 text/html`.
  * Contains `Werkzeug`, `Console Locked`, `PIN`.
  * Must not implement any real console behavior.
* `/debug-blog`

  * Returns `200 text/html`.
  * Contains benign text about debugging.
  * Must not trigger a finding.
* `/debug`

  * Returns `404 text/html`.
  * Contains a branded 404 page.
  * Must not trigger a finding.
* `/fake-powered-by`

  * Returns `200 text/html`.
  * Header `X-Powered-By: PHP/8.2`.
  * Must not trigger a finding.
* `/login-redirect-profiler`

  * Returns `302` to `/login`.
  * Must not become confirmed without debug markers.

### `juice-shop`

Use only as a negative or integration fixture unless a debug page is intentionally added in test mode. Juice Shop should not be assumed to expose framework debug pages by default.

### `dvwa`

Use only as a negative or integration fixture unless a controlled debug route is added. Do not infer PHP or framework from hostname.

### `webgoat`

Use only as a negative or integration fixture unless a controlled debug route is added. Do not infer Java/Spring from hostname.

Fixture requirements:

* All fixture secrets must be fake.
* Fixture debug pages must be static.
* No fixture route may execute commands, read local files, or expose host environment.
* The fixture must be deterministic across runs.
* The fixture must support both positive and negative tests.

## Acceptance criteria

The implementation is acceptable when:

* The check is fully deterministic.
* The check uses shared `ScanTarget` and `Evidence`.
* Only `FrameworkDebugPageSignature` and `FrameworkDebugPageFinding` are defined by this spec.
* The runner sends only read-only requests.
* The runner respects `max_requests`, timeouts, response-size limits, and shared retry policy.
* The runner stays within target scope.
* The runner never interacts with debug consoles beyond loading the page.
* The runner does not download large sensitive artifacts such as heap dumps.
* The runner detects at least Django Debug Toolbar, Symfony Profiler, Laravel Debugbar, Rails info routes, Spring Boot Actuator, ELMAH, ASP.NET trace, Werkzeug debugger, Yii debugger, and Apache status/info when fixture evidence is present.
* The runner avoids known false positives, including generic debug text, branded 404 pages, login redirects, `X-Powered-By` alone, and normal error pages.
* Every confirmed finding has at least one evidence record.
* Evidence snippets are redacted and truncated according to shared policy.
* Findings are idempotent across repeated runs.
* Stale findings can be marked when evidence no longer reproduces.
* TLS errors, connection errors, timeouts, and unsupported content types are handled gracefully.
* No real OpenRouter, AI, browser automation, or external network dependency is required for tests.
* Unit tests cover signature matching, false positives, persistence shape, safety restrictions, request budget, stale behavior, and fixture integration.
* The check completes within the configured budget on the dedicated fixture.
* Failure in one candidate path does not abort the full check unless the scan orchestrator cancels the target.

