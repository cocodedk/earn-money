---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 1
spec: 22
slug: config-files
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 1.22 Config files

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

Detect publicly reachable application, framework, build, deployment, and service configuration files that may expose internals such as routes, package names, database drivers, cloud settings, container metadata, debug flags, or credentials. The runner cares because these files often turn a low-noise information leak into a direct attack path, even when the target does not expose an obvious error page or admin panel.

## Inputs

The runner receives a shared `ScanTarget` and uses only its normalized URL, scope rules, and shared HTTP client settings.

Optional knobs:

| Name                       |      Type |                          Default | Description                                                                                 |
| -------------------------- | --------: | -------------------------------: | ------------------------------------------------------------------------------------------- |
| `max_paths`                |   integer |                            `120` | Maximum candidate config paths to test per target origin.                                   |
| `request_timeout_ms`       |   integer |                        inherited | Per-request timeout. Use the shared default unless overridden by the runner.                |
| `max_body_bytes`           |   integer |                          `65536` | Maximum response bytes retained for signature matching and evidence.                        |
| `follow_redirects`         |   boolean |                          `false` | Do not follow redirects by default. A redirect is evidence only for the requested path.     |
| `include_low_signal_paths` |   boolean |                          `false` | Enables noisy generic names such as `/config` and `/settings`.                              |
| `custom_paths`             |  string[] |                             `[]` | Extra in-scope paths supplied by the caller. Must be relative or same-origin absolute URLs. |
| `allowed_statuses`         | integer[] |                     `[200, 206]` | Status codes that may confirm exposure when paired with matching content.                   |
| `near_miss_statuses`       | integer[] | `[301, 302, 307, 308, 401, 403]` | Status codes that may create candidate findings but not confirmed findings.                 |

The runner must not require credentials. If credentials are available from a broader authenticated scan mode, this stub still runs only against paths allowed by the shared scope and must mark evidence as authenticated in the shared `Evidence` metadata if the shared schema supports it.

Candidate paths are deterministic and grouped by ecosystem. Keep the first version small and explainable.

Core path set:

```text
/application.yml
/application.yaml
/application.properties
/bootstrap.yml
/bootstrap.yaml
/config.yml
/config.yaml
/config.json
/config.php
/config.inc.php
/settings.php
/settings.json
/appsettings.json
/appsettings.Development.json
/web.config
/app.config
/local.settings.json
/.config
/config/config.yml
/config/config.yaml
/config/default.json
/config/production.json
/config/development.json
/config/settings.json
/settings/local.py
/settings/production.py
/conf/application.conf
/conf/app.conf
/conf/server.xml
/WEB-INF/web.xml
/META-INF/context.xml
/docker-compose.yml
/docker-compose.yaml
/docker-compose.override.yml
/.docker/config.json
/kubernetes.yml
/kubernetes.yaml
/k8s.yml
/k8s.yaml
/helm/values.yaml
/values.yaml
/ansible.cfg
/inventory.ini
/terraform.tfvars
/terraform.tfstate
/.npmrc
/.yarnrc
/.pypirc
/pip.conf
/composer.json
/package.json
/package-lock.json
/pnpm-lock.yaml
/yarn.lock
/requirements.txt
/pyproject.toml
/Pipfile
/Gemfile
/Gemfile.lock
/go.mod
/go.sum
/Cargo.toml
/Cargo.lock
/pom.xml
/build.gradle
/settings.gradle
/.editorconfig
```

`custom_paths` are appended after the core path set, deduplicated, normalized, and capped by `max_paths`.

## Detection logic

Use deterministic HTTP checks only.

### Request method

For each candidate path:

1. Normalize the path against the `ScanTarget` origin.
2. Reject out-of-scope absolute URLs.
3. Send `GET` with the shared scanner user agent.
4. Set `Accept` to prefer text-like content:

```text
Accept: text/plain,text/yaml,application/yaml,application/json,application/xml,text/xml,text/*,*/*;q=0.1
```

5. Do not send payloads.
6. Do not use `POST`, `PUT`, `PATCH`, `DELETE`, or WebDAV methods.
7. Do not follow redirects unless `follow_redirects=true`.

`HEAD` is optional as a preflight only when the shared HTTP client already supports it. A `HEAD` response must never confirm a finding by itself because it has no body pattern evidence.

### Response gating

A response is eligible for body signature checks when all are true:

* status is in `allowed_statuses`
* response body length is greater than `0`
* response body retained length is at least enough for one configured signature
* content type is text-like, JSON-like, XML-like, YAML-like, Java properties-like, TOML-like, or missing
* body is not mostly binary

Treat a response as mostly binary when either condition is true:

* first retained chunk contains `NUL` bytes
* more than 30% of sampled bytes are non-printable and not common whitespace

A response with `401` or `403` may produce a `candidate` finding only when the path is highly specific, such as `/WEB-INF/web.xml`, `/appsettings.json`, or `/terraform.tfstate`. It must not be `confirmed` without readable body content.

A redirect may produce a `candidate` finding only when the `Location` header keeps the same sensitive filename or clearly points to an access-control flow. Generic redirects to `/`, `/login`, or marketing pages must be rejected.

### Negative control checks

Many sites return branded 200 pages for missing files. The runner must compare suspicious responses against at least one negative control path per origin.

Generate a random control path with the same extension family where practical:

```text
/__scanner_missing_config_<random>.yaml
/__scanner_missing_config_<random>.json
/__scanner_missing_config_<random>.php
```

Use the control response to reject soft-404s.

Reject a candidate when any of these are true:

* candidate body is near-identical to the negative control body
* candidate body has the same title and same dominant text as the negative control HTML page
* candidate body is a generic SPA shell, index page, login page, marketing page, WAF page, or CDN error page
* candidate body contains no config-like syntax or known config keys
* candidate path returns HTML and the only match is the requested filename echoed in a page template

Similarity can be simple and deterministic:

* exact normalized body hash match
* same status plus same `Content-Length`
* Jaccard similarity over normalized word tokens above `0.90`
* shared HTML `<title>` plus no config signatures

### Signature matching

A confirmed finding requires a path-sensitive body match. Do not confirm from filename alone.

Use signatures that combine:

* requested path or extension
* status code
* content type
* syntax markers
* config keys
* secret-like keys
* ecosystem-specific markers

Stub-specific signature type:

```ts
export type ConfigFileSignature = {
  id: string;
  family:
    | "spring"
    | "dotnet"
    | "php"
    | "python"
    | "java"
    | "node"
    | "ruby"
    | "go"
    | "rust"
    | "docker"
    | "kubernetes"
    | "terraform"
    | "ansible"
    | "package"
    | "generic";
  paths: string[];
  extensions: string[];
  required_statuses: number[];
  content_type_hints: string[];
  required_patterns: string[];
  optional_patterns: string[];
  secret_key_patterns: string[];
  negative_patterns: string[];
  min_required_matches: number;
  confidence: "low" | "medium" | "high";
};
```

Suggested first-version signatures:

| Family       | Paths / extensions                                           | Required body evidence                                                                                       | Confidence                                                   |
| ------------ | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------ |
| `spring`     | `application.yml`, `application.properties`, `bootstrap.yml` | `spring:`, `server.port`, `spring.datasource`, `management.endpoints`, or Java property syntax               | `high`                                                       |
| `dotnet`     | `appsettings*.json`, `web.config`, `local.settings.json`     | JSON object with `ConnectionStrings`, `Logging`, `AllowedHosts`, `Kestrel`, or XML `<configuration>`         | `high`                                                       |
| `php`        | `config.php`, `settings.php`, `config.inc.php`               | PHP opening tag plus config assignments such as `$db`, `$database`, `$config`, `DB_HOST`, `DB_NAME`          | `high`                                                       |
| `python`     | `settings/*.py`, `config.py`                                 | Django/Flask-style assignments such as `SECRET_KEY`, `DATABASES`, `INSTALLED_APPS`, `DEBUG`, `ALLOWED_HOSTS` | `high`                                                       |
| `java`       | `web.xml`, `context.xml`, `application.conf`                 | XML or HOCON config tags such as `<web-app`, `<Context`, `play.http`, `akka.`                                | `high`                                                       |
| `node`       | `config/*.json`, `package.json`, `.npmrc`                    | package metadata or config keys such as `scripts`, `dependencies`, `registry=`, `_authToken`                 | `medium` for package metadata, `high` for auth token markers |
| `docker`     | `docker-compose*.yml`                                        | `services:`, `image:`, `ports:`, `environment:`, `volumes:`                                                  | `high`                                                       |
| `kubernetes` | `kubernetes.yaml`, `k8s.yaml`, `values.yaml`                 | `apiVersion:`, `kind:`, `metadata:`, `spec:`, Helm `image:` / `service:` blocks                              | `high`                                                       |
| `terraform`  | `terraform.tfvars`, `terraform.tfstate`                      | `terraform_version`, `resources`, `outputs`, provider settings, `variable` assignments                       | `high`                                                       |
| `ansible`    | `ansible.cfg`, `inventory.ini`                               | `[defaults]`, `[inventory]`, host group syntax, `ansible_host`, `ansible_user`                               | `medium`                                                     |
| `package`    | lockfiles and manifests                                      | valid package manifest markers and dependency lists                                                          | `medium`                                                     |
| `generic`    | `config.yml`, `settings.json`, `.config`                     | config-like key/value syntax plus at least two non-generic keys                                              | `medium`                                                     |

Secret-like keys raise severity and confidence but are not required to detect a config file:

```text
password
passwd
pwd
secret
secret_key
api_key
apikey
access_key
private_key
client_secret
token
auth_token
bearer
connection_string
database_url
db_password
aws_access_key_id
aws_secret_access_key
azure_storage_connection_string
```

Secret detection must be conservative. Match key names and nearby non-empty values, but do not print full values in summaries. Store only redacted snippets in `Evidence` unless the shared evidence store explicitly supports sensitive evidence.

### Finding classification

Status rules:

* `confirmed`: readable config-like body, path-sensitive signature match, and not soft-404.
* `candidate`: sensitive path exists but body is blocked, redirected to access control, truncated before enough evidence, or has weak generic config evidence.
* `rejected`: response is missing, generic, binary, soft-404, out-of-scope, or lacks config evidence.
* `stale`: previously confirmed finding no longer reproduces in the current run.

Confidence rules:

* `high`: specific filename plus specific parser/syntax evidence, or secret-like key with config syntax.
* `medium`: specific filename plus generic config syntax, package manifest exposure, or blocked access to a highly sensitive config path.
* `low`: weak evidence from generic path names, redirects, or ambiguous text. Low confidence must not be reported as confirmed.

Severity suggestion is deterministic and app-owned:

| Condition                                                                                    | Suggested severity |
| -------------------------------------------------------------------------------------------- | ------------------ |
| confirmed config with credential-like keys and non-empty values                              | `high`             |
| confirmed deployment/runtime config with internal services, ports, routes, or cloud metadata | `medium`           |
| confirmed package/build manifest without secrets                                             | `low`              |
| blocked or redirected sensitive config path                                                  | `info`             |
| weak candidate with ambiguous evidence                                                       | `info`             |

The final severity policy lives outside this stub.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Stub-specific finding type:

```ts
export type ConfigFilesFinding = {
  id: string;
  target: ScanTarget;
  status: "candidate" | "confirmed" | "rejected" | "stale";
  confidence: "low" | "medium" | "high";
  severity_suggestion: "info" | "low" | "medium" | "high" | "critical";
  url: string;
  path: string;
  http_status: number | null;
  content_type: string | null;
  content_length: number | null;
  detected_family: ConfigFileSignature["family"] | "unknown";
  matched_signature_ids: string[];
  matched_patterns: string[];
  secret_key_names: string[];
  redaction_applied: boolean;
  soft_404_checked: boolean;
  negative_control_url: string | null;
  negative_control_similarity: number | null;
  evidence: Evidence[];
  first_seen_at: string;
  last_seen_at: string;
};
```

Persistence rules:

* Store one finding per target origin and exposed config URL.
* Attach evidence for request metadata, response status, selected headers, and redacted body snippet.
* Evidence body snippets must be capped by `max_body_bytes`.
* Redact suspected secret values before storing snippets in normal evidence.
* Store matched key names such as `DB_PASSWORD`, not full secret values, unless the shared secure evidence mechanism requires exact raw capture.
* Stable finding identity should use target origin plus normalized path plus signature family.
* Re-running the scan must update `last_seen_at` instead of creating duplicates.
* If a previous confirmed finding is now missing or rejected, mark it `stale` according to the shared lifecycle rules.

Example evidence summary fields, using the shared `Evidence` shape:

```json
{
  "kind": "http_response",
  "source": "GET /appsettings.json",
  "summary": "Readable .NET appsettings file with ConnectionStrings and Logging sections. Secret-like values redacted.",
  "redacted": true
}
```

## Safety

This stub is read-only.

Allowed behavior:

* same-origin `GET`
* optional same-origin `HEAD`
* deterministic response parsing
* deterministic redaction
* deterministic soft-404 comparison
* evidence storage through shared persistence

Forbidden behavior:

* no mutation methods
* no request bodies
* no form submission
* no login attempt
* no credential use unless the enclosing authenticated scan mode already supplies an approved session
* no brute force
* no recursive directory enumeration
* no path traversal payloads
* no backup filename mutation beyond the fixed candidate path list and caller-provided `custom_paths`
* no use of discovered credentials
* no calls to URLs found inside config files
* no LLM interpretation of exposed config contents

Payload discipline:

* Candidate paths are static strings or caller-supplied in-scope paths.
* Do not generate permutations such as `.bak`, `~`, `.old`, or date-stamped backups here. Those belong in the backup-files stub.
* Do not append query strings intended to bypass caches, auth, routing, or WAF behavior.
* Do not attempt encoded variants such as `%2e`, double slashes, or traversal.

PII and secret handling:

* Treat readable config files as sensitive.
* Redact values for keys matching `secret_key_patterns`.
* Keep enough redacted context to prove the issue.
* Do not include full secrets in logs, summaries, terminal output, test snapshots, or report text.
* Do not use leaked credentials for follow-up checks.

AI involvement: `None`.

Deterministic gap: none for the first version. If a later implementation adds AI-assisted classification for unknown config formats, it must only run after deterministic evidence capture, must receive redacted evidence, and must not change finding status without deterministic support.

## Pass/fail check

A run passes when all assertions below hold.

Positive assertions:

* The scanner requests each configured candidate path with `GET` only.
* The scanner stays within the `ScanTarget` origin and scope.
* A readable `/appsettings.json` response containing a JSON object with `ConnectionStrings` creates a `confirmed` finding.
* A readable `/application.yml` response containing `spring:` or `spring.datasource` creates a `confirmed` finding.
* A readable `/WEB-INF/web.xml` response containing `<web-app` creates a `confirmed` finding.
* A readable `/docker-compose.yml` response containing `services:` and `image:` creates a `confirmed` finding.
* A readable `/terraform.tfstate` response containing `terraform_version` or `resources` creates a `confirmed` finding.
* A blocked `/WEB-INF/web.xml` with status `403` creates at most a `candidate` finding with no body-based confirmation.
* A confirmed response with secret-like keys stores redacted evidence and records the matched key names.
* A package manifest such as `/package.json` with dependency metadata is reported at no more than `low` severity suggestion unless secret-like keys are present.
* Negative control requests are made for eligible text-like positive responses.
* Soft-404 responses are rejected.
* Re-running the same scan updates the existing finding instead of creating a duplicate.

Negative assertions:

* The scanner must not confirm a finding from filename alone.
* The scanner must not confirm a finding from `HEAD` alone.
* The scanner must not confirm a finding when the response body matches the negative control body.
* The scanner must not confirm a finding when a missing config path returns the SPA index page.
* The scanner must not report generic login pages, WAF block pages, CDN errors, or marketing pages as config files.
* The scanner must not follow off-origin redirects.
* The scanner must not use `POST`, `PUT`, `PATCH`, `DELETE`, WebDAV, or request bodies.
* The scanner must not recursively crawl directories after finding a config file.
* The scanner must not generate backup-file mutations such as `.bak`, `.old`, `~`, or `.save`.
* The scanner must not print or persist full secret values in normal logs or report summaries.
* The scanner must not use values found in config files for later authenticated checks.
* The scanner must not hard-code hostname-specific expectations.
* The scanner must not call an LLM for detection, confirmation, severity, or redaction.

Fixture-level assertions:

```text
Given /appsettings.json returns 200 application/json with {"ConnectionStrings":{"Default":"Server=db;Password=test-secret"}}
Then the scanner creates one confirmed ConfigFilesFinding
And detected_family is dotnet
And confidence is high
And severity_suggestion is high
And secret_key_names includes a password-like key
And stored evidence does not contain "test-secret"

Given /missing-appsettings.json and the negative control both return the same SPA shell
Then the scanner creates no confirmed finding

Given /WEB-INF/web.xml returns 403
Then the scanner creates at most one candidate finding
And confidence is medium or low
And severity_suggestion is info
And no body signature is recorded

Given /package.json returns a normal package manifest without secrets
Then the scanner creates a confirmed or candidate finding according to configured policy
And severity_suggestion is low
And it does not claim credential exposure
```

## Test fixtures

Use a new fixture slug: `config-files`.

Reason: common public training apps do not consistently expose representative config files, and the scanner needs deterministic positive and negative cases without adding real secrets.

Fixture behavior:

| Route                                     | Status | Content type               | Body                                                                           | Expected                                                           |
| ----------------------------------------- | -----: | -------------------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| `/appsettings.json`                       |  `200` | `application/json`         | .NET-style JSON with `ConnectionStrings`, `Logging`, and fake password value   | confirmed, high confidence, redacted                               |
| `/application.yml`                        |  `200` | `text/yaml`                | Spring-style YAML with `spring.datasource.url` and `server.port`               | confirmed, high confidence                                         |
| `/WEB-INF/web.xml`                        |  `200` | `application/xml`          | Minimal Java web descriptor with `<web-app>`                                   | confirmed, high confidence                                         |
| `/docker-compose.yml`                     |  `200` | `text/yaml`                | Compose file with `services`, `image`, `ports`, and fake environment variable  | confirmed, high confidence                                         |
| `/terraform.tfstate`                      |  `200` | `application/json`         | Minimal fake state with `terraform_version`, `resources`, and redaction target | confirmed, high confidence                                         |
| `/package.json`                           |  `200` | `application/json`         | Package manifest with dependencies and scripts, no secrets                     | confirmed or candidate, medium confidence, low severity suggestion |
| `/WEB-INF/blocked.xml`                    |  `403` | `text/html`                | Access denied body                                                             | candidate only                                                     |
| `/config.yml`                             |  `200` | `text/html`                | SPA shell identical to negative control                                        | rejected                                                           |
| `/settings.json`                          |  `200` | `text/html`                | Login page                                                                     | rejected                                                           |
| `/binary.config`                          |  `200` | `application/octet-stream` | Binary bytes with NUL values                                                   | rejected                                                           |
| `/__scanner_missing_config_<random>.yaml` |  `200` | `text/html`                | Same SPA shell as `/config.yml`                                                | negative control                                                   |

Fixture constraints:

* All secrets are fake and clearly marked as test values.
* The fixture must not expose real environment variables.
* Bodies should be small and stable.
* Routes should be served by a simple static container or minimal HTTP handler.
* The fixture must support deterministic assertions without network access outside the test container.

Existing fixtures may still be used for regression smoke tests:

* `juice-shop`: optional negative/control run to make sure normal SPA routes are not misreported as config files.
* `dvwa`: optional PHP environment smoke test only if it exposes safe, intentional config-like content in the test container.
* `webgoat`: optional Java environment smoke test only if it exposes safe, intentional metadata in the test container.

Do not depend on optional fixtures for the core acceptance test.

## Acceptance criteria

Implementation is acceptable when:

* It uses shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`.
* It defines only `ConfigFileSignature` and `ConfigFilesFinding` as stub-specific types.
* It performs only read-only in-scope requests.
* It uses deterministic signatures and soft-404 checks.
* It confirms findings only from readable response evidence, never from path names alone.
* It records `candidate`, `confirmed`, `rejected`, and `stale` states according to the shared lifecycle.
* It assigns only `low`, `medium`, or `high` confidence.
* It redacts secret-like values before normal persistence, logging, and reporting.
* It keeps matched secret key names for audit without exposing full values.
* It handles TLS errors, connection errors, timeouts, redirects, binary bodies, compressed responses, and malformed text without crashing.
* It finishes within the configured request and path budget.
* It is idempotent across repeated scans.
* It has no flaky retries. Retry only through the shared HTTP retry policy, if one exists.
* It does not hard-code expected technologies by hostname.
* It does not call AI.
* It includes unit tests for signature matching, soft-404 rejection, redaction, scope enforcement, and finding lifecycle.
* It includes integration tests against the `config-files` fixture.
* It includes negative tests proving that SPA shells, login pages, WAF pages, binary files, and blocked pages are not confirmed as exposed config files.

<!-- Context note: scanner LLM/action safety constraints are consistent with the project guidance in the uploaded OpenRouter-backed scanner design. :contentReference[oaicite:0]{index=0} -->

