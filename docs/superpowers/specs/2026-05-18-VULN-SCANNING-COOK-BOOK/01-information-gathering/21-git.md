---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 1
spec: 21
slug: git
status: done        # pending | in-progress | blocked | done — absorbed into stub well_known_paths (registered under spec 1.20)
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 1.21 `.git`

> Phase 1 — Information gathering · Category: Sensitive files

> **Closure (2026-05-20):** Absorbed by stub `well_known_paths` (registered owner: spec [1.20](./20-env.md)). The `git` family in that stub handles `.git/HEAD`, `.git/config`, `.git/index`, `.git/objects/info/packs`, and other Git control files per this spec's `## Detection logic`.

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

Detect exposed Git repository metadata under a web root, mainly `/.git/HEAD`, `/.git/config`, `/.git/index`, and `/.git/objects/info/packs`. A reachable `.git` directory can disclose source code, commit history, internal paths, remotes, author emails, secrets committed in history, and deployment details. The runner cares because even a single readable Git control file is strong evidence that repository material may be exposed, but the scanner must prove this with small read-only probes and must not try to dump the repository.

## Inputs

The runner receives a shared `ScanTarget` from `../00-shared-schema.md`.

Required input:

* `ScanTarget` with the base URL, normalized origin, scan scope, timeout policy, TLS policy, and optional authenticated HTTP context if the wider scan is already authenticated.

Optional config knobs:

| Name                                  |             Default | Purpose                                                                      |
| ------------------------------------- | ------------------: | ---------------------------------------------------------------------------- |
| `git_probe_enabled`                   |              `true` | Enables this check.                                                          |
| `git_probe_paths`                     |           see below | Relative paths to probe.                                                     |
| `git_max_requests_per_target`         |                 `4` | Hard cap for default mode.                                                   |
| `git_request_timeout_ms`              | shared HTTP default | Per-request timeout.                                                         |
| `git_text_body_cap_bytes`             |              `8192` | Maximum stored/read text bytes per response.                                 |
| `git_binary_body_cap_bytes`           |                `16` | Maximum bytes read for binary magic checks.                                  |
| `git_follow_redirects`                |  `same-origin-only` | Never follow cross-origin redirects.                                         |
| `git_include_directory_listing_probe` |              `true` | Probe `/.git/` for directory listing evidence.                               |
| `git_probe_logs_head`                 |             `false` | Disabled by default because Git reflogs may contain author names and emails. |
| `git_store_sanitized_config_excerpt`  |              `true` | Store a redacted config excerpt when needed for proof.                       |

Default probe order:

1. `/.git/HEAD`
2. `/.git/config`
3. `/.git/index`
4. `/.git/objects/info/packs`
5. `/.git/` only when `git_include_directory_listing_probe=true`

Do not add dynamic object paths, branch names, pack file names, or repository-specific paths to the default probe list.

Credentials:

* Use only the HTTP context already approved for the `ScanTarget`.
* Do not prompt for new credentials.
* Do not use credentials discovered in responses.
* Do not retry with altered authentication state.

## Detection logic

Detection is deterministic. The runner makes bounded read-only HTTP requests and classifies only from response evidence.

### Request rules

For each configured path:

* Build the URL by joining the normalized target origin/base path with the relative probe path.
* Use `GET`.
* Send no request body.
* Use the shared scanner user agent.
* Use normal cache-busting only if the shared HTTP layer already does so.
* Follow only same-origin redirects when enabled.
* Treat cross-origin redirects as non-evidence.
* Stop once the request cap is reached.
* Stop early when a high-confidence confirmed finding has enough evidence.

Never infer exposure from hostname, framework, status page text, CDN, server banner, or known product defaults.

### Positive signatures

#### `/.git/HEAD`

A response is a Git HEAD signature when all of these are true:

* Final URL path is still equivalent to `/.git/HEAD`.
* Status code is `200`.
* Body is small text.
* Body, after trimming ASCII whitespace, matches one of:

```text
^ref: refs/(heads|tags|remotes)/[A-Za-z0-9._/\-]+$
^[a-fA-F0-9]{40}$
^[a-fA-F0-9]{64}$
```

Classification:

* `confirmed`, `high` when the body matches `ref: refs/...`.
* `confirmed`, `high` when the body is a 40-character or 64-character commit hash.
* `candidate`, `medium` only if the response is truncated before the full line can be checked but starts with a valid Git HEAD prefix such as `ref: refs/`.

#### `/.git/config`

A response is a Git config signature when all of these are true:

* Final URL path is still equivalent to `/.git/config`.
* Status code is `200`.
* Body is text.
* Body contains Git config section syntax and at least one Git-specific key.

Strong patterns:

* `[core]`
* `repositoryformatversion`
* `filemode`
* `bare`
* `logallrefupdates`
* `[remote "origin"]`
* `url =`

Classification:

* `confirmed`, `high` when `/.git/config` matches and `/.git/HEAD` also matched.
* `confirmed`, `high` when the config contains `[core]` plus two or more Git-specific keys.
* `candidate`, `medium` when only a partial config-like response is visible.
* `rejected`, `low` when the response is an HTML app page, login page, JSON error, or generic “not found” page despite status `200`.

Before persistence, redact config values that may contain credentials:

* URL userinfo, for example `https://user:pass@example.com/repo.git`
* access tokens in URL paths, queries, or fragments
* values containing `token`, `password`, `secret`, `apikey`, `api_key`, `authorization`, or `credential`

#### `/.git/index`

A response is a Git index signature when all of these are true:

* Final URL path is still equivalent to `/.git/index`.
* Status code is `200`.
* First four bytes are `DIRC`.

Classification:

* `confirmed`, `high`.

Persistence rule:

* Do not store file names from the index by default.
* Store only binary magic result, content hash, byte count, content type, and response metadata.
* If a debug mode later stores names, it must be a separate explicit feature with stricter PII handling.

#### `/.git/objects/info/packs`

A response is a Git pack-info signature when all of these are true:

* Final URL path is still equivalent to `/.git/objects/info/packs`.
* Status code is `200`.
* Body contains one or more lines matching:

```text
^P pack-[a-fA-F0-9]{40}\.pack$
^P pack-[a-fA-F0-9]{64}\.pack$
```

Classification:

* `confirmed`, `high` when at least one valid pack line is found.
* `candidate`, `medium` when the path is reachable but the body is empty. Empty pack-info can exist in an unpacked repository, but it is not enough alone.

Do not fetch the referenced `.pack` or `.idx` files.

#### `/.git/`

A response is a Git directory listing signature when all of these are true:

* Final URL path is still equivalent to `/.git/` or `/.git`.
* Status code is `200`.
* Body is HTML or plain text.
* Body contains directory listing evidence for Git files.

Strong patterns:

* `<title>Index of /.git`
* `Index of /.git`
* links or rows for `HEAD`, `config`, `objects/`, `refs/`

Classification:

* `confirmed`, `high` when listing contains at least two Git entries such as `HEAD` and `objects/`.
* `candidate`, `medium` when listing contains only one Git-like entry.
* `rejected`, `low` for SPA fallback pages, marketing pages, login forms, generic 200 pages, or JSON API responses.

### Negative and rejection logic

Reject a possible match when any of these are true:

* Status is `404`, `410`, or another clear not-found response.
* Status is `401` or `403`; this means the path may exist but is not exposed to this scan context.
* Status is `3xx` to a different origin.
* Final response is a login page, SSO page, CAPTCHA, WAF block page, or generic app shell.
* Body is HTML and does not contain directory-listing evidence.
* Body contains the literal probe path but no Git syntax.
* Response comes from a custom error page with status `200`.
* Evidence only shows `.gitignore`, not `.git`.

A protected `/.git/HEAD` returning `403` is not a vulnerability finding for this check. The runner may store non-finding telemetry if the shared schema supports it, but it must not create a `GitFinding`.

### Finding construction

Create one finding per `ScanTarget` and exposed Git location. Merge signatures from multiple probe paths into the same finding when they share the same origin and base path.

Status rules:

* `confirmed` when any high-confidence signature is found.
* `candidate` when only medium-confidence partial evidence exists.
* `rejected` only for internal test/assertion records if the persistence layer keeps rejected findings.
* `stale` when a previously confirmed finding no longer reproduces in the current scan.

Confidence rules:

* `high`: valid `HEAD`, valid `index`, valid pack-info, or strong directory listing.
* `medium`: partial `HEAD`, partial config, empty pack-info with other weak indicators.
* `low`: reserved for rejected or stale records; do not emit new low-confidence `.git` exposure findings by default.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Define only these stub-specific types:

```ts
export type GitComponent =
  | "head"
  | "config"
  | "index"
  | "objects_info_packs"
  | "directory_listing";

export type GitMatchType =
  | "git_head_ref"
  | "git_head_detached_sha1"
  | "git_head_detached_sha256"
  | "git_config_core"
  | "git_config_remote"
  | "git_index_dirc"
  | "git_pack_info"
  | "git_directory_listing";

export type GitSignature = {
  component: GitComponent;
  match_type: GitMatchType;
  path: string;
  final_url: string;
  method: "GET";
  status_code: number;
  content_type?: string;
  bytes_read: number;
  body_truncated: boolean;
  content_hash: string;
  matched_excerpt?: string;
  redaction_applied: boolean;
  confidence: "low" | "medium" | "high";
  evidence_id: string;
};

export type GitFinding = {
  target_id: string;
  status: "candidate" | "confirmed" | "rejected" | "stale";
  confidence: "low" | "medium" | "high";
  title: "Exposed Git repository metadata";
  exposed_base_path: string;
  signatures: GitSignature[];
  evidence_ids: string[];
  first_seen_at?: string;
  last_seen_at?: string;
  remediation: {
    summary: string;
    steps: string[];
  };
};
```

Persistence requirements:

* Store each HTTP response as shared `Evidence`.
* Store only capped bodies or sanitized excerpts.
* Store binary evidence as metadata plus hash, not raw binary.
* Redact Git config excerpts before saving them.
* Link every `GitSignature` to an `Evidence` record.
* Keep raw response bodies only if the shared evidence store is approved for sensitive data. Otherwise store hashes, headers, status, and sanitized excerpts.
* Do not persist discovered remote credentials, tokens, author emails from reflogs, or index file names unless a later explicit feature requires it.

Recommended remediation text:

* Remove `.git` from the web root.
* Add server rules denying access to `/.git/` and all children.
* Rebuild/deploy from a clean artifact rather than a working copy.
* Rotate any secrets that may have been committed.
* Review web server aliases, static file roots, and container image build context.
* Add a regression test or deployment check that blocks public `/.git/HEAD`.

## Safety

This check is read-only.

Allowed behavior:

* Bounded `GET` requests to fixed Git metadata paths.
* Same-origin redirects only.
* Small response reads with strict byte caps.
* Sanitized evidence storage.
* Deterministic matching.

Forbidden behavior:

* No `POST`, `PUT`, `PATCH`, `DELETE`, or WebDAV methods.
* No request bodies.
* No `git clone`.
* No use of tools such as `git-dumper`, `wget --mirror`, or recursive downloaders.
* No fetching `/.git/objects/<sha>`.
* No fetching `.pack` or `.idx` files.
* No brute forcing branches, refs, commits, object IDs, or filenames.
* No reading `/.git/logs/HEAD` by default.
* No credential harvesting.
* No use of credentials found in Git config.
* No cross-origin redirect following.
* No classification based on hostname or expected technology.

PII and secret handling:

* Git config may contain remote URLs with usernames, passwords, or tokens. Redact before persistence.
* Git index may contain internal file paths. Do not store parsed index entries by default.
* Reflogs may contain author names and emails. Do not probe reflogs by default.
* Store enough evidence to prove exposure without collecting repository contents.

AI involvement: `None`.

There is no deterministic gap that needs AI for this check. Matching, confidence, status, redaction, and remediation text are all rule-based.

## Pass/fail check

### Positive assertions

The implementation passes when all of these are true:

* Given `GET /.git/HEAD` returns `200` and body `ref: refs/heads/main\n`, the runner creates one `GitFinding` with:

  * `status = "confirmed"`
  * `confidence = "high"`
  * one `GitSignature` with `component = "head"`
  * `match_type = "git_head_ref"`
  * linked shared `Evidence`

* Given `GET /.git/HEAD` returns `200` and a 40-character hex body, the runner creates a confirmed high-confidence finding with `match_type = "git_head_detached_sha1"`.

* Given `GET /.git/HEAD` returns `200` and a 64-character hex body, the runner creates a confirmed high-confidence finding with `match_type = "git_head_detached_sha256"`.

* Given `GET /.git/index` returns `200` and starts with bytes `DIRC`, the runner creates a confirmed high-confidence finding and does not persist parsed file names.

* Given `GET /.git/config` returns a valid Git config containing `[core]`, `repositoryformatversion`, and `filemode`, the runner creates a confirmed high-confidence finding or merges it into the existing `.git` finding.

* Given `GET /.git/objects/info/packs` returns `P pack-<40 hex chars>.pack`, the runner creates a confirmed high-confidence finding and does not fetch the referenced pack file.

* Given `GET /.git/` returns an index page listing `HEAD`, `config`, and `objects/`, the runner creates a confirmed high-confidence finding.

* Given multiple positive probes on the same target, the runner creates one merged finding with multiple signatures, not duplicate findings.

* Given a previously confirmed finding no longer reproduces, the runner marks it `stale` according to the shared finding lifecycle rules.

### Negative assertions

The implementation must not do any of these:

* Must not create a finding when `/.git/HEAD` returns `404`.
* Must not create a finding when `/.git/HEAD` returns `403`.
* Must not create a finding when `/.git/HEAD` returns a generic HTML app shell with status `200`.
* Must not create a finding when `/.git/HEAD` redirects to `/login` and the final response is a login page.
* Must not create a finding when only `/.gitignore` is accessible.
* Must not create a finding from the word “git” appearing in a normal page.
* Must not create a finding from server header, hostname, framework, or CDN evidence alone.
* Must not follow a redirect from `https://target.example/.git/HEAD` to another origin.
* Must not request `/.git/objects/<sha>`.
* Must not request `.pack` or `.idx` files.
* Must not run `git clone` or any repository reconstruction tool.
* Must not parse and persist Git index filenames by default.
* Must not store unredacted remote URLs containing credentials.
* Must not make more than `git_max_requests_per_target` requests in default mode.
* Must not call an LLM.

### Error-handling assertions

* TLS errors are recorded using the shared error/evidence pattern and do not crash the scan.
* Timeouts are recorded and do not trigger unbounded retries.
* Malformed responses are rejected unless a deterministic signature still matches.
* Binary responses are capped and hashed.
* The check is idempotent: repeated scans against the same fixture produce the same finding status, confidence, and signature set.

## Test fixtures

Use a new fixture slug unless an existing fixture already exposes `.git` safely.

Recommended fixture: `git-exposure`.

The fixture should be a small static HTTP service with these routes:

| Route                          | Response                                                             | Expected result                      |
| ------------------------------ | -------------------------------------------------------------------- | ------------------------------------ |
| `/.git/HEAD`                   | `200 text/plain`, `ref: refs/heads/main\n`                           | confirmed, high                      |
| `/.git/config`                 | `200 text/plain`, minimal Git config with a redacted-test remote URL | confirmed, high, sanitized           |
| `/.git/index`                  | `200 application/octet-stream`, starts with `DIRC`                   | confirmed, high, no filenames stored |
| `/.git/objects/info/packs`     | `200 text/plain`, one valid pack line                                | confirmed, high, no pack fetch       |
| `/.git/`                       | `200 text/html`, index listing with `HEAD`, `config`, `objects/`     | confirmed, high                      |
| `/spa/.git/HEAD`               | `200 text/html`, normal app shell                                    | no finding                           |
| `/forbidden/.git/HEAD`         | `403`                                                                | no finding                           |
| `/missing/.git/HEAD`           | `404`                                                                | no finding                           |
| `/login-redirect/.git/HEAD`    | `302 /login`, login HTML                                             | no finding                           |
| `/external-redirect/.git/HEAD` | `302 https://other.example/.git/HEAD`                                | no follow, no finding                |
| `/.gitignore`                  | `200 text/plain`                                                     | no `.git` finding                    |

Fixture requirements:

* Do not include a real repository.
* Do not include real secrets.
* Do not include real author names or emails.
* Use synthetic remote URLs such as `https://user:password@example.invalid/repo.git` to test redaction.
* Add server-side request logging so tests can assert that pack files, object files, and reflogs were not requested.

Existing training fixtures:

* `juice-shop`, `dvwa`, and `webgoat` should be negative fixtures unless deliberately configured to expose `.git`.
* Do not modify those apps to expose a real repository. Use the static `git-exposure` fixture instead.

## Acceptance criteria

The implementation is acceptable when:

* It uses shared `ScanTarget` and `Evidence`.
* It defines only `GitSignature` and `GitFinding` as stub-specific types.
* It performs deterministic read-only detection.
* It sends only bounded `GET` requests.
* It completes the default check in no more than four probe requests, or five when directory listing probe is enabled.
* It finishes within the shared per-target scan budget.
* It handles TLS errors, connection errors, timeouts, and malformed responses without crashing.
* It does not perform recursive downloads or repository reconstruction.
* It does not fetch Git objects, pack files, index files beyond the magic/header check, or reflogs by default.
* It redacts sensitive Git config values before persistence.
* It stores minimal binary evidence as metadata and hash.
* It rejects SPA fallbacks, login pages, WAF pages, and custom 200 error pages.
* It emits clear `candidate`, `confirmed`, `rejected`, or `stale` status according to the rules above.
* It uses `low | medium | high` confidence exactly.
* It never hard-codes hostname-to-technology assumptions.
* It does not call AI.
* It has unit tests for every positive and negative assertion in this spec.
* It has fixture tests proving that no unsafe paths were requested.
* Re-running the scanner against the same fixture is stable and does not create duplicate findings.

