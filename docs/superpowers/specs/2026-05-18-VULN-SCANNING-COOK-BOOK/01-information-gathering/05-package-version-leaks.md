---

# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 1
spec: 5
slug: package-version-leaks
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 1.5 Package/version leaks

> Phase 1 — Information gathering · Category: Technology fingerprinting

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

Detect publicly exposed package manifests, lockfiles, dependency metadata, source maps, and static asset comments that disclose package names or exact versions. A runner cares because these leaks improve later vulnerability matching, dependency risk checks, exploit-prioritization, and technology fingerprinting without needing invasive tests.

## Inputs

The runner receives a shared `ScanTarget` and writes shared `Evidence` records for every response that supports or rejects a finding.

Required input:

| Field         |            Type | Notes                                                                                           |
| ------------- | --------------: | ----------------------------------------------------------------------------------------------- |
| `target`      |    `ScanTarget` | Base URL, host, IP, and target status come from the shared schema.                              |
| `http_client` | internal client | Must support redirects, timeout, TLS handling, response size caps, and raw header/body capture. |
| `run_id`      |          string | Links evidence and findings to one scan run.                                                    |

Optional config:

| Field                               |         Default | Notes                                                                                                          |
| ----------------------------------- | --------------: | -------------------------------------------------------------------------------------------------------------- |
| `max_candidate_paths`               |            `80` | Hard cap on direct file probes.                                                                                |
| `max_response_bytes`                |        `524288` | Read at most 512 KiB per candidate file unless shared runner config overrides it.                              |
| `request_timeout_ms`                |          `5000` | Per-request timeout.                                                                                           |
| `follow_redirects`                  |   `same-origin` | Follow only same-origin redirects.                                                                             |
| `include_source_map_checks`         |          `true` | Probe source maps only when referenced by fetched JS or CSS evidence.                                          |
| `include_static_asset_comment_scan` |          `true` | Parse already-discovered JS/CSS/text assets for package banners.                                               |
| `credentials`                       |          `None` | This spec is unauthenticated for MVP. Do not use credentials unless a future RoE profile explicitly allows it. |
| `respect_robots_txt`                | project default | Follow the shared runner rule if one exists. This spec does not require robots bypass.                         |

The runner may also receive previously collected evidence from specs `1.1` through `1.4`, especially HTML, JavaScript, CSS, headers, and discovered asset URLs. Reuse that evidence before making new requests.

## Detection logic

All detection is deterministic. Do not call an LLM.

### Candidate sources

Detect package/version leaks from three sources:

1. Known dependency files at common public paths.
2. Static assets already linked by the application.
3. Source maps referenced by static assets.

### Direct path probes

Make `GET` requests only. Do not use `POST`, `PUT`, `PATCH`, `DELETE`, or custom payloads.

Probe a small fixed list of high-signal paths under the target base URL. Do not recurse directories. Do not brute-force large wordlists.

Recommended path list:

```text
/package.json
/package-lock.json
/npm-shrinkwrap.json
/yarn.lock
/pnpm-lock.yaml
/bower.json
/composer.json
/composer.lock
/requirements.txt
/requirements-dev.txt
/Pipfile
/Pipfile.lock
/poetry.lock
/pyproject.toml
/setup.py
/Gemfile
/Gemfile.lock
/Cargo.toml
/Cargo.lock
/go.mod
/go.sum
/pom.xml
/build.gradle
/build.gradle.kts
/gradle.properties
/packages.config
/project.assets.json
/.csproj
/package.xml
/mix.exs
/mix.lock
/rebar.config
/rebar.lock
/Podfile
/Podfile.lock
/pubspec.yaml
/pubspec.lock
/deno.json
/deno.lock
/import_map.json
```

Rules:

* Normalize paths against `ScanTarget.base_url`.
* Keep requests same-origin.
* Apply the response size cap before parsing.
* Store each response as shared `Evidence`, including status code, URL, content type, content hash, truncation flag, and redirect chain if available.
* Treat `200`, `203`, and `206` as parseable.
* Treat `401` and `403` as non-leaking protected candidates unless the body itself exposes package/version data.
* Treat `404`, `410`, and empty bodies as negative evidence, not findings.
* Treat redirects to login pages, home pages, or generic SPA shells as negative unless content parsing confirms a dependency file.

### Static asset comment scan

Scan fetched JavaScript, CSS, source map, and plain text evidence for dependency banners.

Use existing evidence first:

* HTML script URLs.
* CSS URLs.
* JS chunks from framework detection.
* Asset URLs found in previous phase-1 specs.
* Source map URLs discovered from `sourceMappingURL`.

Also scan new direct responses from candidate files.

Match common banner forms:

```text
/*! package-name v1.2.3 */
/*!
 * package-name 1.2.3
 */
/** @license React v17.0.2 */
/*! lodash 4.17.21 */
```

Extract:

* package name
* version
* source kind
* URL
* byte range or line range where possible
* evidence ID

Do not report a package only because a word appears in prose. Require a package-like token and a version-like token near each other.

### Source map checks

Only probe source map URLs if one of these is true:

* A fetched JS or CSS asset contains a `sourceMappingURL` comment.
* A previously collected asset URL ends with `.map`.
* The candidate path is directly linked from fetched HTML or JS.

Accepted source map evidence:

* JSON body with `"version"`, `"sources"`, or `"names"`.
* Content type such as `application/json`, `application/octet-stream`, or `text/plain` with valid source map JSON.
* Body contains package paths such as `node_modules/<name>/`, `webpack://`, `npm/`, or dependency file fragments.

For source maps, extract package names and versions only when the source map includes a version-bearing package path or embedded package metadata. If the source map only reveals file paths without versions, store evidence but do not create a version-leak finding.

### File-specific parsers

Use tolerant parsers. If strict parsing fails, fall back to line-based extraction and mark confidence lower.

#### npm and JavaScript

Files:

* `package.json`
* `package-lock.json`
* `npm-shrinkwrap.json`
* `yarn.lock`
* `pnpm-lock.yaml`
* `bower.json`

Extract:

* package manager
* direct dependencies
* dev dependencies when present
* lockfile package versions
* root project name/version only if the app publishes it publicly
* package manager version if present

Confidence:

* `high`: valid JSON/YAML/lock parser extracted exact package and version.
* `medium`: tolerant parser extracted exact package and version.
* `low`: version-like banner or lock fragment found but file format is incomplete or truncated.

#### Python

Files:

* `requirements.txt`
* `requirements-dev.txt`
* `Pipfile`
* `Pipfile.lock`
* `poetry.lock`
* `pyproject.toml`
* `setup.py`

Extract exact versions from pinned dependencies:

```text
Django==4.2.7
Flask==3.0.0
requests==2.31.0
```

Do not report unpinned ranges as exact version leaks:

```text
Django>=4.2
requests~=2.31
```

For version ranges, create only a package-hint signature with `version = null` and confidence `low`, unless the shared product model does not support versionless hints. In that case, store evidence only.

#### PHP

Files:

* `composer.json`
* `composer.lock`

Prefer `composer.lock` because it contains resolved versions.

Extract:

* `packages[].name`
* `packages[].version`
* `packages-dev[].name`
* `packages-dev[].version`

For `composer.json`, exact versions are usually lower confidence unless pinned.

#### Ruby

Files:

* `Gemfile`
* `Gemfile.lock`

Prefer `Gemfile.lock`.

Extract gem lines from `GEM` sections:

```text
rails (7.0.8)
rack (2.2.8)
```

#### Java and JVM

Files:

* `pom.xml`
* `build.gradle`
* `build.gradle.kts`
* `gradle.properties`

Extract group, artifact, and version when all are present.

Examples:

```text
org.springframework.boot:spring-boot-starter-web:3.2.1
<groupId>org.apache.struts</groupId>
<artifactId>struts2-core</artifactId>
<version>2.5.30</version>
```

If the version is inherited from a parent or variable that cannot be resolved from the same response evidence, store evidence only or produce a `low` confidence hint with `version = null`.

#### Go

Files:

* `go.mod`
* `go.sum`

Extract module paths and versions:

```text
github.com/gin-gonic/gin v1.9.1
golang.org/x/crypto v0.17.0
```

#### Rust

Files:

* `Cargo.toml`
* `Cargo.lock`

Prefer `Cargo.lock`.

Extract crate name and version from lock packages.

#### .NET

Files:

* `packages.config`
* `project.assets.json`
* `.csproj` paths only when directly exposed

Extract:

```xml
<package id="Newtonsoft.Json" version="13.0.3" />
<PackageReference Include="Serilog" Version="3.1.1" />
```

Do not enumerate arbitrary `.csproj` names. Only request exact known direct paths if already linked or listed by other evidence.

### Normalization

Normalize extracted package/version pairs before persistence:

* Trim whitespace.
* Lowercase package ecosystem names, not package names if the ecosystem is case-sensitive.
* Preserve original package name in `raw_package_name`.
* Preserve original version in `raw_version`.
* Normalize semantic versions where safe:

  * Strip leading `v` only into `normalized_version`.
  * Preserve prerelease/build suffixes.
* Keep package manager or ecosystem:

  * `npm`
  * `python`
  * `php-composer`
  * `ruby`
  * `maven`
  * `gradle`
  * `go`
  * `rust`
  * `dotnet`
  * `ios-cocoapods`
  * `dart`
  * `elixir`
  * `erlang`
  * `unknown`

### Confirmation rules

Create a finding only when at least one exact package name and exact version is extracted from public response evidence.

Finding confidence:

| Confidence | Required evidence                                                                                                                    |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `high`     | Valid known package file or lockfile parsed with exact versions.                                                                     |
| `medium`   | Exact package/version extracted from recognizable but partially parsed dependency file, static asset banner, or source map metadata. |
| `low`      | Exact package/version appears in weak context, truncated file, or ambiguous static text, but still has deterministic evidence.       |

Finding status:

| Status      | Meaning                                                                                                       |
| ----------- | ------------------------------------------------------------------------------------------------------------- |
| `candidate` | Extracted package/version exists, but evidence is weak or parser confidence is low.                           |
| `confirmed` | Public dependency file, lockfile, source map, or package banner clearly exposes exact versions.               |
| `rejected`  | Candidate URL looked promising but parsed as unrelated content, login page, SPA shell, or generic error page. |
| `stale`     | Previously confirmed leak no longer appears in current run.                                                   |

Default status:

* `confirmed` for `high` and `medium` confidence exact version leaks.
* `candidate` for `low` confidence exact version leaks.
* `rejected` for path probes that returned plausible names but no parseable dependency evidence.
* `stale` only when comparing against a previous persisted finding for the same target/package/source path.

## Persistence

Use shared `ScanTarget` and shared `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Persist one `Evidence` row per fetched response or reused body slice that supports parsing. Findings refer to evidence IDs.

### `PackageVersionLeakSignature`

A signature is one extracted package/version item from one evidence source.

```json
{
  "id": "uuid",
  "target_id": "uuid",
  "run_id": "uuid",
  "evidence_id": "uuid",
  "source_url": "https://example.test/package-lock.json",
  "source_path": "/package-lock.json",
  "source_kind": "dependency_file | lockfile | static_asset_banner | source_map | static_asset_metadata",
  "ecosystem": "npm | python | php-composer | ruby | maven | gradle | go | rust | dotnet | ios-cocoapods | dart | elixir | erlang | unknown",
  "package_manager": "npm | yarn | pnpm | pip | poetry | pipenv | composer | bundler | cargo | go-mod | maven | gradle | nuget | cocoapods | pub | mix | rebar | unknown",
  "raw_package_name": "lodash",
  "normalized_package_name": "lodash",
  "raw_version": "4.17.21",
  "normalized_version": "4.17.21",
  "version_is_exact": true,
  "dependency_scope": "runtime | development | test | build | transitive | unknown",
  "parser_name": "npm-package-lock-v3",
  "parser_version": "1",
  "matched_text_sha256": "sha256 hex string or null",
  "line_start": 10,
  "line_end": 10,
  "byte_start": 120,
  "byte_end": 155,
  "confidence": "low | medium | high",
  "created_at": "ISO-8601"
}
```

Required fields:

* `id`
* `target_id`
* `run_id`
* `evidence_id`
* `source_url`
* `source_kind`
* `ecosystem`
* `raw_package_name`
* `normalized_package_name`
* `raw_version`
* `normalized_version`
* `version_is_exact`
* `confidence`
* `created_at`

`version_is_exact` must be `true` for a version-leak finding. Versionless package hints may be stored as signatures only if the implementation already supports non-finding signatures.

### `PackageVersionLeakFinding`

A finding groups one or more signatures that disclose package versions from the same source or same package.

```json
{
  "id": "uuid",
  "target_id": "uuid",
  "run_id": "uuid",
  "title": "Public package versions exposed",
  "status": "candidate | confirmed | rejected | stale",
  "confidence": "low | medium | high",
  "severity": "info",
  "summary": "The target exposes package metadata with exact dependency versions.",
  "source_urls": [
    "https://example.test/package-lock.json"
  ],
  "evidence_ids": [
    "uuid"
  ],
  "signature_ids": [
    "uuid"
  ],
  "ecosystems": [
    "npm"
  ],
  "package_count": 42,
  "sample_packages": [
    {
      "package": "lodash",
      "version": "4.17.21",
      "ecosystem": "npm",
      "source_kind": "lockfile"
    }
  ],
  "risk_note": "Exact dependency versions can help match known vulnerabilities and tune later checks.",
  "recommendation": "Remove public access to dependency manifests, lockfiles, source maps, and build metadata unless they are intentionally published.",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

Rules:

* `severity` is always `info` for this phase-1 fingerprinting finding.
* Do not assign CVEs here. CVE matching belongs in a later dependency-vulnerability phase.
* Cap `sample_packages` to 10 entries.
* Preserve all package/version signatures separately even when the finding summary samples only 10.
* Grouping strategy for MVP:

  * one finding per target per source URL, or
  * one finding per target per ecosystem if that matches existing persistence style.
* The finding must always include at least one `evidence_id` and one `signature_id`.
* Do not persist raw full dependency files inside the finding. Store raw bodies only through the shared evidence store and existing retention rules.

### Deduplication

Deduplicate signatures by:

```text
target_id + source_url + ecosystem + normalized_package_name + normalized_version
```

Deduplicate findings by:

```text
target_id + source_url + source_kind
```

If the same package/version appears in several files, keep separate signatures because each source is useful evidence.

## Safety

This check is read-only.

Allowed behavior:

* `GET` same-origin candidate files.
* `GET` same-origin static assets already linked by the target.
* `HEAD` may be used only if the shared HTTP client already uses it for cheap metadata checks, but `GET` is still required before parsing.
* Follow same-origin redirects within the configured redirect limit.
* Reuse previously collected evidence.

Disallowed behavior:

* No `POST`, `PUT`, `PATCH`, `DELETE`, or state-changing methods.
* No login attempts.
* No credential use for MVP.
* No directory brute force.
* No recursive crawling.
* No package registry lookups.
* No CVE database lookups.
* No exploit checks.
* No dependency confusion checks.
* No requests to third-party URLs found inside files.
* No arbitrary source map guessing beyond direct `sourceMappingURL` references or already discovered `.map` asset URLs.
* No hostname-specific expectations.
* No hard-coded mapping such as “Juice Shop must expose npm”.
* No storing cookies, tokens, or secrets in findings.

PII and secret handling:

* Dependency files may accidentally contain private repository URLs, usernames, tokens, or internal paths.
* Before logging parser errors or matched snippets, pass snippets through existing redaction utilities.
* Do not print full dependency files to logs.
* Store full response bodies only if the shared evidence policy allows it.
* `sample_packages` must include package names and versions only, not repository URLs or authors.

AI involvement:

```text
AI: None
```

No deterministic gap requires AI. If a parser cannot understand a dependency format, mark the candidate as unsupported or low-confidence evidence. Do not ask an LLM to infer package versions.

## Pass/fail check

The implementation passes when all assertions below are true.

### Positive assertions

* Given a public `package-lock.json` with `lodash` version `4.17.21`, the runner creates:

  * one shared `Evidence` record for the response,
  * one `PackageVersionLeakSignature`,
  * one `PackageVersionLeakFinding`,
  * `confidence = high`,
  * `status = confirmed`,
  * `severity = info`.
* Given a public `composer.lock`, the runner extracts exact package names and versions from `packages` and `packages-dev`.
* Given a public `requirements.txt` containing `Django==4.2.7`, the runner extracts `Django` and `4.2.7`.
* Given a public JS asset with `/*! lodash 4.17.21 */`, the runner creates a `medium` confidence signature.
* Given a fetched JS asset with `//# sourceMappingURL=main.js.map` and a same-origin source map exposing exact package versions, the runner stores source-map evidence and signatures.
* Every finding contains at least one `evidence_id`.
* Every finding contains at least one `signature_id`.
* Every exact version signature has `version_is_exact = true`.
* The runner can reuse previously fetched HTML, JS, CSS, and header evidence instead of re-fetching the same URL.
* Re-running the check against the same target does not create duplicate active findings for the same `target_id + source_url + source_kind`.

### Negative assertions

* The runner must not create a finding for a `404` response.
* The runner must not create a finding for a generic SPA shell returned from `/package.json`.
* The runner must not create a finding for a login page returned from `/composer.lock`.
* The runner must not create a finding for unpinned Python ranges such as `Django>=4.2` as an exact version leak.
* The runner must not create a finding when only a framework name is present without a version.
* The runner must not call package registries, GitHub, npm, PyPI, Maven Central, or any third-party URL.
* The runner must not follow cross-origin redirects.
* The runner must not request arbitrary `.map` guesses such as `app.js.map` unless a fetched asset references that map or the URL was already discovered.
* The runner must not use credentials.
* The runner must not assign CVEs.
* The runner must not change severity based on package names.
* The runner must not send response bodies or package metadata to an LLM.
* The runner must not log full package files, cookies, tokens, or secret-looking values.
* The runner must not hard-code fixture hostnames or assume a specific target exposes a specific ecosystem.

### Stale assertion

If a previous run confirmed `/package-lock.json` and the current run receives `404` or unrelated content for the same source URL, the previous active finding is marked `stale` or superseded according to the shared persistence rules.

## Test fixtures

Use `juice-shop` for the MVP fixture because it is a Node/JavaScript application and naturally supports npm package metadata.

Required fixture behavior:

| Fixture      | Feature                                                                                                                         | Expected result                                  |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| `juice-shop` | Expose a controlled test `package.json` or `package-lock.json` through the fixture container route used only for scanner tests. | Confirmed npm package/version leak.              |
| `juice-shop` | Serve a JS asset containing a package banner such as `/*! lodash 4.17.21 */`.                                                   | Medium-confidence static asset banner signature. |
| `juice-shop` | Serve a JS asset with same-origin `sourceMappingURL` and a source map containing package metadata.                              | Source-map evidence and signatures.              |
| `juice-shop` | Return the SPA shell for `/missing-package.json`.                                                                               | No finding.                                      |
| `juice-shop` | Return `404` for `/composer.lock`.                                                                                              | No finding.                                      |

Add a small synthetic fixture if changing Juice Shop is too noisy:

```text
fixture: package-leak-lab
```

`package-leak-lab` should expose:

```text
/package-lock.json       -> valid npm lockfile with two exact dependencies
/requirements.txt        -> one pinned and one unpinned dependency
/static/app.js           -> JS banner with one package/version
/static/app.js.map       -> source map referenced by app.js
/fake/package.json       -> HTML shell, not JSON
```

Expected synthetic fixture findings:

* `/package-lock.json`: confirmed, high confidence.
* `/requirements.txt`: confirmed only for pinned dependency.
* `/static/app.js`: confirmed or candidate depending on grouping, medium confidence.
* `/static/app.js.map`: confirmed if exact versions are present.
* `/fake/package.json`: rejected or no finding.

## Acceptance criteria

The implementation is acceptable when:

* It is deterministic and does not call an LLM.
* It only performs read-only same-origin requests.
* It respects the configured request cap, timeout, redirect policy, and response size cap.
* It reuses shared `ScanTarget` and shared `Evidence`.
* It defines only `PackageVersionLeakSignature` and `PackageVersionLeakFinding` as stub-specific types.
* It extracts exact package/version pairs from at least npm lockfiles, Composer lockfiles, Python pinned requirements, Go modules, Cargo lockfiles, and JS/CSS package banners.
* It handles invalid JSON, invalid lockfiles, binary responses, oversized responses, TLS errors, and timeouts without crashing the scan.
* It stores evidence for parseable responses and links findings to evidence.
* It produces no finding for missing files, login pages, SPA shells, unpinned ranges, or package names without versions.
* It does not perform CVE matching or vulnerability claims.
* It does not leak secrets or full dependency file bodies into normal logs.
* It is idempotent across repeated runs.
* It completes within the phase-1 budget for a normal target:

  * no more than `max_candidate_paths` direct probes,
  * no recursive crawling,
  * no third-party requests,
  * no unbounded retries.
* Unit tests cover parser success, parser failure, negative responses, source map handling, deduplication, stale handling, and safety constraints.
* Integration tests pass against the selected fixture without hostname-specific assumptions.

