# Phase 3 Design - Active Recon + Daily Digest

**Date:** 2026-05-12
**Status:** Design for implementation planning
**Scope:** Umbrella architecture for Phase 3 sub-phases 3a, 3b, 3c, and 3d

## 1. Overview

Phase 3 turns the Phase 1 registry and Phase 2 passive asset store into a cautious active-recon loop. It adds scoped HTTP probing, standard nuclei checks, crawling, low-volume content discovery, a triage engine that creates human-review candidates, and an 08:00 daily digest with a phone ping. Active traffic only runs on the VPS, only for programs whose `scope.md` policy is `rate-limited-OK`, and only against assets that pass the current in-scope and out-of-scope checks at run time.

## 2. Architecture Diagram

```
programs/<platform>/<slug>/scope.md
        |
        v
+-------------------+        +------------------+
| flags + policy    | -----> | active runners   |
| RECON_ENABLED     |        |                  |
| FROZEN            |        | 1. httpx         |
| rate-limited-OK   |        | 2. nuclei        |
+-------------------+        | 3. katana        |
        |                    | 4. ffuf          |
        |                    +------------------+
        |                              |
        |                              v
        |              recon/outputs/<platform>/<slug>/<tool>/<date>/<run_id>/
        |                              |
        |                              v
        |                    programs/<platform>/<slug>/db.sqlite
        |                    assets, recon_runs, findings
        |                              |
        v                              v
+-------------------+        +------------------+
| passive assets    | -----> | 7. triage engine |
| from Phase 2      |        | dedupe by hash   |
+-------------------+        +------------------+
                                      |
                                      v
                              findings/_queue/
                                      |
                                      v
                         human gate: queue -> verified
                                      |
                                      v
                         human gate: verified -> submitted

                 +--------------------+
                 | 5. daily digest    |
                 | ops/daily-digest.md|
                 +--------------------+
                            |
                            v
                 +--------------------+
                 | 6. phone ping      |
                 | claude-chat bus    |
                 +--------------------+
```

The runners do not write findings. They write raw artifacts, normalized weak signals, and run metadata. The triage engine is a separate cron job that correlates those signals with the asset DB and deduplicates candidates into `findings/_queue/`.

## 3. Unit-by-Unit Design

### Shared Active Runner Contract

Phase 3 active runners mirror `src/earn_money/runners/passive_recon.py`: short-lived cron entry points, thin subprocess wrappers, typed result dataclasses, and no daemon state. The initial implementation shells out to the installed tools directly. A wrapper may delegate to `clawpwn` later only if it preserves the same runner contract and safety gates.

Each active runner exposes:

```
run_program(paths, platform, slug, *, tool_run=...) -> ActiveRunResult
```

Every `run_program` follows this call order before any target traffic:

1. `flags.require_recon_enabled(paths)`
2. `flags.require_program_not_frozen(paths, platform, slug)`
3. `s = scope.read_scope(paths.scope_file(platform, slug))`
4. `policy.require_policy_allows(s, mode="active")`
5. Load candidate assets or URLs, then filter every target with `scope.is_in_scope(..., s.in_scope, s.out_of_scope)`

The shared result shape includes `run_id`, `targets_considered`, `targets_scanned`, `artifacts_written`, `outputs_recorded`, `source_failures`, and `terminated_reason` (one of `null`, `kill_switch`, `freeze`, `timeout`).

#### Per-request scope enforcement

A pre-flight in-scope filter on the *initial* target list is not sufficient. Active tools follow redirects, crawl links, and discover paths during a run. Every runner must also enforce scope on every URL or host it touches after startup:

- **httpx**: ProjectDiscovery httpx does not follow redirects by default; the opt-in `-fr` / `-follow-redirects` / `-follow-host-redirects` flags must never appear in the runner's argv. If a target returns 3xx, the parser records the redirect target in `redirect_to` and the triage engine decides downstream whether to add it as a new candidate. The e2e test in Task 12 empirically proves the no-follow guarantee.
- **nuclei**: pass `-disable-redirects`. Templates that require redirect-following are explicitly disallowed in the approved profile.
- **katana**: invoke with `-scope-all-hosts=false` plus an explicit `-fs` (field scope) and `-cs` (crawl scope) regex derived from `s.in_scope` and `s.out_of_scope` at run start. After katana exits, the wrapper filters every emitted URL through `scope.is_in_scope` again before any signal is written; OOS URLs are silently dropped and counted in `oos_drops`.
- **ffuf**: invoke with `-fr` (filter regex) and `-fc` (filter codes) plus a `-r` (follow-redirects) flag set to **false**. Every match the wrapper consumes is re-checked against `scope.is_in_scope`. Wordlists must not contain absolute URLs.

The wrapper rejects any tool output line that resolves to an OOS host, even if the tool produced it. OOS leakage is a configuration bug — the wrapper records it in the manifest under `oos_drops`, and a non-zero `oos_drops` count emits a `recon_anomalies` signal that surfaces in the daily digest.

#### Batch contract

A **batch** is one subprocess invocation. The wrapper splits the input target list into batches with explicit bounds:

- **Max batch size:** 50 targets per subprocess (configurable per runner, never more than 200).
- **Max batch duration:** 5 minutes wall-clock for httpx; 25 minutes for nuclei (the full template profile takes longer at -rl 10); 10 minutes for katana/ffuf. Beyond the cap, the wrapper sends SIGTERM, waits 5s, then SIGKILL.

A **kill-switch watchdog** runs as a background thread inside the wrapper for the duration of every subprocess. It polls `RECON_ENABLED` and the per-program `FROZEN` flag every 5 seconds. If either state changes mid-batch — flag removed, FROZEN appears, or the file is replaced — the watchdog:

1. SIGTERMs the in-flight subprocess immediately, waits 5s, then SIGKILLs.
2. Marks the current `recon_runs` row `status=partial` with `terminated_reason` set (`kill_switch` or `freeze`).
3. Writes a final manifest and exits with the corresponding non-zero exit code.

The watchdog also fires between batches (same checks, same handling). This bounds the worst-case window between operator pulling the kill-switch and active traffic stopping to **~10 seconds** (one poll interval plus SIGTERM grace), not to one full batch duration.

#### Failure taxonomy

Every runner classifies failures into five disjoint buckets. Counters and exit codes follow:

| Class | Examples | Counter | Exit |
| --- | --- | --- | --- |
| **Config failure** (before traffic) | missing binary, unapproved template profile, missing wordlist, scope file unreadable | n/a (fail closed) | non-zero, no artifacts |
| **Target failure** | DNS error, TLS error, single 5xx, single timeout | `source_failures` per target | 0, run `partial` |
| **Batch failure** | batch subprocess timed out or crashed | `source_failures` += batch size, anomaly signal | 0, run `partial` |
| **Parser failure** | non-JSONL line, schema mismatch | per-line, log to stderr, anomaly signal if >1% of lines | 0, run `partial` |
| **Artifact / DB failure** | cannot write manifest, SQLite locked > N seconds, disk full | fatal | non-zero |

Config failures **must fail closed before any subprocess starts**. The runner exits with a clear stderr message and never opens the network.

### Shared Artifact Contract

Raw outputs land under:

```
recon/outputs/<platform>/<slug>/<tool>/<YYYY-MM-DD>/<run_id>/
```

Each run directory contains:

- `manifest.json`: run ID, tool, command profile, timestamps, status, counters, and artifact schema version.
- `input.txt`: the exact scoped targets given to the tool.
- `raw.jsonl` or `raw.json`: native tool output, preferably JSON/JSONL when the tool supports it.
- `stderr.txt`: captured stderr.
- `signals.jsonl`: normalized weak signals for triage; empty is valid.

Phase 3a writes only `manifest.json`. The remaining files (`input.txt`, `raw.jsonl`, `stderr.txt`, `signals.jsonl`) are required from Phase 3b onward when triage starts consuming artifacts; they may be empty but must exist.

The triage engine discovers new work from `recon_runs` rows where `triaged_at IS NULL`, not by guessing from filenames. The manifest exists so artifacts remain understandable if the DB is unavailable.

### 3.1 `httpx` Active HTTP Probing Runner

**Purpose:** Convert scoped assets from the Phase 2 `assets` table into live HTTP service observations: scheme, port, status, title, web server, technologies, redirects, TLS summary, and lightweight fingerprints.

**Inputs:**

- `programs/<platform>/<slug>/scope.md`
- `programs/<platform>/<slug>/db.sqlite` `assets` rows
- `RECON_ENABLED` and `programs/<platform>/<slug>/FROZEN`

**Outputs:**

- Raw httpx JSONL under `recon/outputs/<platform>/<slug>/httpx/<YYYY-MM-DD>/<run_id>/raw.jsonl`
- `manifest.json`, `input.txt`, `stderr.txt`, and `signals.jsonl` in the same run directory
- Updates to `assets.ports`, `assets.fingerprint`, and `assets.last_seen`
- A `recon_runs` row with run status, artifact path, counters, and `source_failures`

**Dependencies:**

- ProjectDiscovery `httpx` CLI on the VPS
- `earn_money.scope.is_in_scope`
- `earn_money.policy.require_policy_allows(s, mode="active")`
- `earn_money.flags.require_recon_enabled`
- `earn_money.flags.require_program_not_frozen`

**Failure modes:**

- Missing binary, timeout, DNS drift, TLS errors, WAF blocks, and malformed JSONL.
- Per-target or per-batch failures increment `source_failures` and leave the run `partial` if any targets succeeded.
- A total tool failure writes a failed manifest and exits non-zero.

**Source location:**

- Runner: `src/earn_money/runners/httpx_probe.py`
- Tool wrapper: `src/earn_money/recon/httpx.py`
- CLI: `bin/httpx-probe`

### 3.2 `nuclei` Template-Based Vulnerability Runner

**Purpose:** Run conservative template checks against live HTTP services. This is limited to standard CVE and common misconfiguration templates. No custom exploit chains, no DoS templates, no paid templates, and no autoescalation.

**Inputs:**

- Live HTTP service list from the latest scoped httpx observations
- Current `scope.md`, kill switch, and freeze flag
- Allowed template profile: CVE plus standard misconfiguration templates only

**Outputs:**

- Raw nuclei JSONL under `recon/outputs/<platform>/<slug>/nuclei/<YYYY-MM-DD>/<run_id>/raw.jsonl`
- Normalized `signals.jsonl` entries for template hits
- `recon_runs` row with template count, target count, findings emitted, and `source_failures`

**Dependencies:**

- ProjectDiscovery `nuclei` CLI and local template cache on the VPS
- The httpx service inventory from Phase 3a
- Same flags, scope, and policy gates as httpx

**Failure modes:**

- Template update failures, missing templates, unsafe template categories, target rate limits, malformed output, or CLI timeouts.
- Unsafe template categories are configuration errors and must fail closed before any target traffic.
- Individual target failures do not discard other target results.

**Source location:**

- Runner: `src/earn_money/runners/nuclei_scan.py`
- Tool wrapper: `src/earn_money/recon/nuclei.py`
- CLI: `bin/nuclei-scan`

### 3.3 `katana` Crawler Runner

**Purpose:** Crawl live in-scope web roots to discover endpoints, parameters, forms, JavaScript references, and application surface changes for triage. Katana output is a signal source, not proof of vulnerability.

**Inputs:**

- Current httpx live roots
- Scope rules filtered again before the crawler receives targets
- Conservative crawl limits: shallow depth, per-host request cap, timeout, and robots-aware defaults where supported

**Outputs:**

- Raw katana JSONL under `recon/outputs/<platform>/<slug>/katana/<YYYY-MM-DD>/<run_id>/raw.jsonl`
- Normalized endpoint and parameter signals in `signals.jsonl`
- `recon_runs` row with URLs crawled, endpoints discovered, and `source_failures`

**Dependencies:**

- ProjectDiscovery `katana` CLI on the VPS
- httpx service inventory
- Same flags, scope, and policy gates as httpx

**Failure modes:**

- Spider traps, very large sites, repeated redirects, auth walls, WAF blocks, and malformed output.
- The runner enforces max depth, max duration, and max URLs per host.
- Partial crawls still produce artifacts and are marked `partial`.

**Source location:**

- Runner: `src/earn_money/runners/katana_crawl.py`
- Tool wrapper: `src/earn_money/recon/katana.py`
- CLI: `bin/katana-crawl`

### 3.4 `ffuf` Directory and Content Fuzzer Runner

**Purpose:** Run low-volume content discovery against selected live web roots. This is intentionally the least frequent and most constrained runner because it creates the most target friction.

**Inputs:**

- Current httpx live roots
- Optional high-value base paths from katana
- Committed free wordlists only: SecLists and assetnote subsets approved in the implementation plan
- Scope-filtered target URLs

**Outputs:**

- Raw ffuf JSON under `recon/outputs/<platform>/<slug>/ffuf/<YYYY-MM-DD>/<run_id>/raw.json`
- Normalized discovery signals in `signals.jsonl`
- `recon_runs` row with targets, requests attempted, interesting responses, and `source_failures`

**Dependencies:**

- `ffuf` CLI on the VPS
- Approved local wordlists
- Same flags, scope, and policy gates as httpx

**Failure modes:**

- Soft-404 noise, wildcard responses, WAF blocks, large response variance, missing wordlists, timeout, and rate limiting.
- The runner must auto-calibrate where possible and cap request volume per root.
- Missing or unapproved wordlists fail closed before any traffic.

**Source location:**

- Runner: `src/earn_money/runners/ffuf_scan.py`
- Tool wrapper: `src/earn_money/recon/ffuf.py`
- CLI: `bin/ffuf-scan`

### 3.5 08:00 Daily Digest Generator

**Purpose:** Overwrite `ops/daily-digest.md` every morning with the operator's work queue: what changed, what needs acknowledgement, and which candidates deserve the 30-60 minute manual slot.

**Inputs:**

- Per-program SQLite DBs
- `findings/_queue/`, `_verified/`, `_submitted/`, and `_resolved/`
- `recon_runs` rows from the last digest window
- `programs/*/*/FROZEN`
- `ops/ledger.md` when present

**Outputs:**

- `ops/daily-digest.md`, overwritten on each scheduled run
- A short summary line returned to the phone-ping unit

**Markdown structure:**

```markdown
# Daily Digest - <YYYY-MM-DD> 08:00 Europe/Copenhagen

Summary: <new_assets> new assets, <queue_count> queue candidates, <freeze_count> scope freezes, <failure_count> recon anomalies, ledger <delta>.

## Actions
- [ ] <highest priority operator action>

## New Assets
| Program | Asset | First seen | Source |

## Queue Candidates
| Rank | Candidate | Program | Why it matters | Evidence |

## Recon Anomalies
| Program | Runner | Run | Problem | Next step |

## Scope Diffs Awaiting Ack
| Program | Frozen since | Reason | Ack path |

## Triage Replies Awaiting Response
| Program | Report | Last update | SLA |

## Ledger Delta
| Window | Submitted | Resolved paid | Resolved dupe | Resolved N/A | Amount |

## Runner Health
| Program | Runner | Last run | Status | Source failures |

## Links
- Queue: findings/_queue/
- Verified: findings/_verified/
- Ledger: ops/ledger.md
```

The digest is a view. SQLite and explicit file moves remain the state sources.

**Dependencies:**

- Program DB schema from Phase 3a/3b
- Existing findings directory conventions
- Ledger file when Phase 4 starts using it

**Failure modes:**

- Missing DB, missing findings directories, corrupt run metadata, or absent ledger.
- Missing optional sources produce a visible anomaly row, not a crash, unless the digest cannot be written.

**Source location:**

- Generator: `src/earn_money/ops/digest.py`
- Runner: `src/earn_money/runners/daily_digest.py`
- CLI: `bin/daily-digest`

### 3.6 Phone Ping via Claude-Chat Bus

**Purpose:** Send a small phone notification after the digest is generated. The phone ping tells the operator that the digest is ready; it does not carry raw target evidence or sensitive details.

**Inputs:**

- The digest summary line
- Path to `ops/daily-digest.md`
- Counts for freezes, high-priority candidates, and failed runners

**Message shape:**

```json
{
  "kind": "bug_bounty_daily_digest",
  "created_at": "<ISO-8601 timestamp>",
  "priority": "normal|high",
  "summary": "Bug bounty digest: 2 new assets, 3 queue candidates, 0 freezes, 1 runner anomaly.",
  "deep_link": "ops/daily-digest.md"
}
```

Priority is `high` when there is an active freeze, a triage reply inside its SLA window, or a high-confidence queue candidate. Otherwise it is `normal`.

**Outputs:**

- One claude-chat bus message per digest run
- A row in the per-program SQLite `ops_runs` table (new in Phase 3, see section 4) with `kind="phone_ping"`, `started_at`, `status`, and a short payload digest. This is the *only* place ping state lives — recon manifests stay focused on target traffic.

**Dependencies:**

- Existing claude-chat bus tooling on the VPS
- Daily digest generator

**Failure modes:**

- Bus unavailable, malformed payload, duplicate send, or phone delivery failure.
- Ping failure does not rewrite or invalidate the digest. It is recorded as a runner anomaly for the next digest.

**Source location:**

- Bus wrapper: `src/earn_money/ops/phone_ping.py`
- Runner: `src/earn_money/runners/phone_ping.py`
- CLI: `bin/phone-ping`

### 3.7 Triage Engine

**Purpose:** Read new recon artifacts and the asset DB, correlate weak signals across tools, deduplicate by stable finding hash, and write candidate markdown files into `findings/_queue/`. Triage cannot promote to `_verified/`, cannot submit, and cannot invent mocked findings.

**Runtime model decision:** Phase 3 uses a hybrid model. Runners emit raw output and normalized weak signals, but they do not create findings. A separate cron triage job reads untriaged `recon_runs`, correlates signals across tools, and writes candidates. This preserves unit boundaries, lets triage improve without rerunning active scans, and avoids a pipeline chain where one noisy tool controls the whole run.

**Inputs:**

- `recon_runs` rows where `triaged_at IS NULL`
- Each run's `signals.jsonl`, raw artifacts, and manifest
- `assets` and `findings` tables
- Current `scope.md`, kill switch, and freeze flag

**Outputs:**

- New or updated `findings` rows
- Markdown candidate files in `findings/_queue/<finding_hash>.md`
- Updated `recon_runs.triaged_at`

**Dependencies:**

- SQLite schema additions below
- All runner artifact manifests
- Finding templates for queue notes

**Failure modes:**

- Malformed artifacts, stale scope, duplicate hashes, write conflicts, missing evidence files, or corrupt DB.
- One bad artifact increments `source_failures` for triage and does not block other run IDs.
- If current scope excludes an asset, triage drops the signal and records an anomaly instead of creating a candidate.

**Source location:**

- Engine: `src/earn_money/triage/engine.py`
- Hashing: `src/earn_money/triage/hashing.py`
- Queue writer: `src/earn_money/triage/queue.py`
- Runner: `src/earn_money/runners/triage.py`
- CLI: `bin/triage`

## 4. SQLite Schema Additions

The existing per-program SQLite file remains the source of truth. Phase 3 expands it instead of adding a second database.

### Schema migration

Phase 2 ships `assets` and a six-column `findings` table. Phase 3 must add tables and widen `findings` without breaking Phase 2 DBs that already have data.

The migration is gated by SQLite's `PRAGMA user_version`:

- **v0** — pre-Phase-2 (no migration applies; treat as empty)
- **v1** — Phase 2 schema as currently shipped
- **v2** — Phase 3a additions: `recon_runs`, `http_services`, `signals`, `ops_runs` tables; `assets.fingerprint` and `assets.ports` semantics widened
- **v3** — Phase 3b additions: expanded `findings` columns, `findings_state_history` table

Migration runs at runner startup (every runner, not just the first one) via `earn_money.db.migrate(conn, target_version)`. The migration function:

1. Reads `PRAGMA user_version`.
2. If `< target_version`, runs each pending migration step inside a transaction.
3. Each step uses `ALTER TABLE` for additive column changes and `CREATE TABLE IF NOT EXISTS` for new tables.
4. For non-nullable column additions on existing rows, the migration supplies a literal default (e.g. `severity_hint TEXT NOT NULL DEFAULT 'unknown'`).
5. After all steps succeed, bumps `PRAGMA user_version` to the target inside the same transaction.
6. On failure: rolls back, leaves user_version unchanged, exits with a clear error.

Test contract:

- Unit tests cover each migration step.
- An integration test seeds a Phase 2 DB with realistic rows, runs `migrate(conn, 3)`, and asserts the resulting schema matches Phase 3 plus all original data is preserved.
- A test that runs `migrate(conn, 3)` twice in a row asserts it's idempotent and writes nothing the second time.

### `assets` additions

Existing columns stay in place. Phase 3 widens how `ports` and `fingerprint` are populated, but **the canonical service inventory lives in the new `http_services` table** (see below). The `assets.fingerprint` JSON blob remains as a convenience denormalization, not a source of truth.

- `ports` stores a comma-separated list of observed HTTP(S) ports.
- `fingerprint` stores compact JSON with the latest httpx fingerprint summary, mirrored from the most recent `http_services` row.

### New table: `http_services`

Normalized service inventory keyed by asset + scheme + port. Every nuclei/katana/ffuf invocation reads from this table — not from `assets.fingerprint` JSON.

Concrete columns:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `subdomain TEXT NOT NULL` (foreign reference to `assets.subdomain`)
- `scheme TEXT NOT NULL` (`http` or `https`)
- `port INTEGER NOT NULL`
- `url TEXT NOT NULL` (canonical root: `<scheme>://<subdomain>[:<port>]/`)
- `status_code INTEGER`
- `title TEXT`
- `server TEXT`
- `technologies TEXT` (JSON array of strings)
- `redirect_to TEXT`
- `tls_summary TEXT` (JSON or empty)
- `observed_at TEXT NOT NULL`
- `last_run_id TEXT NOT NULL`
- `in_scope_at_observation INTEGER NOT NULL DEFAULT 1`
- `UNIQUE(subdomain, scheme, port)`

Upserts: each httpx run replaces the row for its `(subdomain, scheme, port)` triple with the latest observation. Stale rows (no observation in the last N days) are kept but the digest flags them as cold.

### New table: `recon_runs`

Concrete columns:

- `run_id TEXT PRIMARY KEY`
- `platform TEXT NOT NULL`
- `slug TEXT NOT NULL`
- `tool TEXT NOT NULL`
- `started_at TEXT NOT NULL`
- `finished_at TEXT`
- `status TEXT NOT NULL`
- `artifact_dir TEXT NOT NULL`
- `input_count INTEGER NOT NULL DEFAULT 0`
- `output_count INTEGER NOT NULL DEFAULT 0`
- `signal_count INTEGER NOT NULL DEFAULT 0`
- `source_failures INTEGER NOT NULL DEFAULT 0`
- `oos_drops INTEGER NOT NULL DEFAULT 0` (count of tool outputs the wrapper dropped via post-tool scope re-check)
- `terminated_reason TEXT` (null on success; one of `kill_switch`, `freeze`, `timeout` when the run was aborted)
- `triaged_at TEXT`
- `error_summary TEXT`

Allowed `status` values:

- `in_progress`: the runner has called `start_run` but not yet `finish_run`; rows in this state are excluded from triage's untriaged query and surface as Runner Health rows in the digest.
- `success`: all planned batches completed.
- `partial`: at least one batch succeeded and at least one failed.
- `failed`: no useful output was produced.
- `skipped`: no targets were eligible after scope filtering.

Policy, kill-switch, and freeze refusals happen before target selection. They may print an operator-facing message and exit with the existing Phase 2-style codes, but they should not create target artifacts.

### Expanded table: `findings`

The existing columns are kept and expanded. Concrete columns:

- `finding_hash TEXT PRIMARY KEY`
- `platform TEXT NOT NULL`
- `slug TEXT NOT NULL`
- `vuln_class TEXT NOT NULL`
- `asset TEXT NOT NULL`
- `target TEXT NOT NULL`
- `signature TEXT NOT NULL`
- `title TEXT NOT NULL`
- `severity_hint TEXT NOT NULL`
- `confidence INTEGER NOT NULL`
- `source_tool TEXT NOT NULL`
- `source_run_id TEXT NOT NULL`
- `evidence_path TEXT NOT NULL`
- `notes_path TEXT NOT NULL`
- `first_seen TEXT NOT NULL`
- `last_seen TEXT NOT NULL`
- `occurrence_count INTEGER NOT NULL DEFAULT 1`
- `current_state TEXT NOT NULL`
- `state_changed_at TEXT NOT NULL`
- `external_report_id TEXT`
- `payout_amount TEXT`
- `payout_currency TEXT`

### New table: `signals`

A durable, queryable index of every normalized signal a runner emits. The triage engine queries this table — it does not parse `signals.jsonl` files at triage time. The JSONL artifact still exists for human review and disaster recovery, but the DB is the source of truth.

Concrete columns:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `run_id TEXT NOT NULL` (FK → `recon_runs.run_id`)
- `tool TEXT NOT NULL`
- `signal_type TEXT NOT NULL` (e.g. `template_match`, `endpoint_discovered`, `content_match`, `fingerprint_drift`)
- `asset TEXT NOT NULL` (normalized; see normalization rules)
- `target TEXT NOT NULL` (normalized; see normalization rules)
- `signature TEXT NOT NULL`
- `payload TEXT NOT NULL` (compact JSON with tool-specific evidence pointers)
- `observed_at TEXT NOT NULL`
- `UNIQUE(run_id, signal_type, asset, target, signature)`

Runners write to `signals.jsonl` AND insert into this table atomically per batch (transaction commits at batch boundary). If the DB write fails, the wrapper treats it as an artifact-class failure (fatal).

### New table: `ops_runs`

Tracks non-recon runs (daily digest, phone ping, freeze ack). Keeps `recon_runs` focused on target-traffic operations.

Concrete columns:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `kind TEXT NOT NULL` (`daily_digest`, `phone_ping`, `freeze_ack`)
- `started_at TEXT NOT NULL`
- `finished_at TEXT`
- `status TEXT NOT NULL` (`success`, `partial`, `failed`)
- `payload_digest TEXT` (short summary or sha256 of payload, not the full payload)
- `error_summary TEXT`

### Finding hash composition

`finding_hash` is `sha256` over this canonical string:

```
v1|<platform>|<slug>|<vuln_class>|<normalized_asset>|<normalized_target>|<signature>
```

The hash does not include run ID, timestamps, evidence path, title, or severity. Those can change without creating a duplicate candidate.

#### Normalization rules

`normalized_asset` and `normalized_target` are derived from raw input with these deterministic transformations:

1. Lowercase the scheme and host components only (e.g. `HTTP://Example.com/Path` → `http://example.com/Path`). Preserve case in path, query, and fragment — many web servers route case-sensitively, and merging `/Path` with `/path` would cause false dedup of distinct findings.
2. Strip default ports: `:80` for `http://`, `:443` for `https://`.
3. Punycode IDN labels via `idna.encode(..., uts46=True)`.
4. Normalize path: remove duplicate slashes (`//` → `/`), resolve `.` and `..` segments, strip trailing slash except on root path `/`.
5. Drop the URL fragment (`#...`).
6. Sort query parameters by key, then by value. Drop empty-value params unless the key is in an allowlist (e.g. `?debug` is meaningful even with no value).
7. Percent-decode unreserved characters per RFC 3986; re-encode reserved characters in a canonical form.

`normalized_asset` is just the hostname (after steps 1, 3). `normalized_target` is the full URL after all seven steps. For non-URL targets (e.g. raw hostnames passed to httpx), `normalized_target == normalized_asset`.

#### Signature composition by tool

- **nuclei**: `<template_id>|<matcher_name>|<extracted_normalized>` — `extracted_normalized` is the matcher's primary captured value normalized via rules 1-7 (or empty string when nuclei produces no extraction).
- **httpx anomaly**: `<signal_type>|<old_fingerprint_sha256_prefix12>|<new_fingerprint_sha256_prefix12>` — fingerprints are hashed and truncated so changes in noise (timestamp headers) don't propagate to the dedup key.
- **katana**: `<endpoint_path_normalized>|<sorted_parameter_names>|<method>` — parameter names sorted alphabetically, methods uppercased.
- **ffuf**: `<path_normalized>|<status_code>|<response_length_bucket>|<content_type_normalized>` — `response_length_bucket` is one of `<1KB`, `1-10KB`, `10-100KB`, `100KB-1MB`, `>1MB` to avoid splitting on jittery body sizes.

Test contract: every tool's signature composition gets two property-based tests — one for collision resistance (10k random distinct findings produce 10k distinct hashes), one for normalization stability (a finding and its semantically equivalent variant hash to the same value).

### Finding state machine

Allowed states:

- `queued`: triage created or refreshed a candidate in `findings/_queue/`.
- `verified`: the operator manually verified the candidate and moved it to `findings/_verified/`.
- `submitted`: the operator ran `bin/submit`; the report is now with the platform.
- `resolved_paid`: platform accepted and paid.
- `resolved_dupe`: platform marked duplicate.
- `resolved_na`: platform rejected or the operator marked not applicable.
- `resolved_info`: platform accepted as informational or no-bounty.
- `archived`: terminal item moved out of the active workset after retention.

Allowed transitions:

- Triage may create `queued`, refresh `last_seen`, increment `occurrence_count`, and update evidence for an existing non-terminal finding.
- Triage may not change `current_state`.
- Operator action may move `queued -> verified`.
- Operator action may move `queued -> resolved_dupe`, `queued -> resolved_na`, or `queued -> resolved_info`.
- `bin/submit` may move `verified -> submitted`.
- Operator action may move `submitted -> resolved_paid`, `submitted -> resolved_dupe`, `submitted -> resolved_na`, or `submitted -> resolved_info`.
- Retention tooling may move any resolved state to `archived`.

## 5. Scheduling

Scheduling runs on the VPS only. Development on the operator laptop is limited to tests, dry runs with mocked tools, and code review.

### Why systemd timers, not cron

A normal Debian crontab cannot mix time zones per entry, doesn't survive missed runs from boots/downtime, and has weak observability. Phase 3 uses **systemd timers + services**, one pair per job. This gives:

- Per-timer `OnCalendar=` with explicit `Timezone=` (or implicit UTC), no ambient assumption.
- `Persistent=true` to catch up after VPS reboots that miss a scheduled run.
- `journalctl -u <unit>` for structured logs per job, with rotation handled by the system.
- `Type=oneshot` services with `TimeoutStartSec=` for hard runtime caps.
- Explicit `After=` ordering between units (triage after active runners, digest after triage, ping after digest).

### Job table

| Unit | OnCalendar | TZ | Hard timeout | Depends on (After=) |
| --- | --- | --- | --- | --- |
| `scope-sync.timer` | `*-*-* *:00:00` (hourly) | UTC | 5 min | none |
| `passive-recon.timer` | `*-*-* 00,06,12,18:10:00` | UTC | 30 min | `scope-sync.service` |
| `httpx-probe.timer` | `*-*-* 00,06,12,18:35:00` | UTC | 30 min | `passive-recon.service` |
| `nuclei-scan.timer` | `*-*-* 02:15:00` | UTC | 90 min | `httpx-probe.service` |
| `katana-crawl.timer` | `*-*-2/2 03:15:00` (every 2 days) | UTC | 90 min | `httpx-probe.service` |
| `ffuf-scan.timer` | `Sun *-*-* 04:20:00` (weekly) | UTC | 90 min | `httpx-probe.service` |
| `triage.timer` | `*-*-* 05:00:00` | UTC | 30 min | `nuclei-scan.service` |
| `daily-digest.timer` | `*-*-* 08:00:00` | Europe/Copenhagen | 5 min | `triage.service` |
| `phone-ping.timer` | `*-*-* 08:05:00` | Europe/Copenhagen | 2 min | `daily-digest.service` |

Triage fires at 05:00 UTC to leave a clean buffer before the digest in both CET and CEST. During CEST, `08:00 Europe/Copenhagen = 06:00 UTC`, giving triage one full hour to complete. During CET, the gap is two hours. The 30-minute hard timeout on triage further guarantees it finishes before the digest under either timezone.

### Concurrency, locks, and missed-run semantics

SQLite handles concurrent readers fine but serializes writers. To prevent runner pile-ups:

- **Per-program write lock.** Each runner acquires a `BEGIN IMMEDIATE` transaction on the per-program DB at the start of each batch's DB-write phase. Concurrent runners on the same program serialize naturally.
- **Per-runner busy lock.** Each systemd service writes a `/run/earn_money/<runner>.lock` PID file at start; if the lock exists and points to a live process, the service exits with a clear "already running" status. This catches the case where a previous invocation is still alive when the next timer fires.
- **Digest excludes in-flight runs.** The digest queries only `recon_runs` rows with `status IN ('success', 'partial', 'failed', 'skipped')` AND `finished_at IS NOT NULL`. Rows still in flight surface as `Runner Health → in_progress` rows, not as missing data.
- **Persistent timers backfill at most once.** `Persistent=true` makes systemd run a missed timer once after a reboot, not catch up to every missed slot. This prevents a 24-hour outage producing 4 stacked httpx runs.

### Manual invocation

All active runners also support manual invocation on the VPS for incident response or implementation verification: `bin/<runner> --program <slug>` runs the same code path as the timer-driven unit. Manual invocation still acquires the busy lock, still checks `RECON_ENABLED`, freeze flags, scope, and policy, and still writes a `recon_runs` row.

## 6. Sub-Phase Implementation Roadmap

### 3a - Active Runner Foundation + httpx

Ships the shared active-runner conventions and the first active runner:

- Artifact directory layout and `manifest.json` contract
- `recon_runs` schema and tests
- Thin subprocess wrapper pattern for active tools
- `httpx` runner and CLI
- Scope, policy, kill-switch, freeze, and source-failure tests

Dependency: Phases 1 and 2.

### 3b - nuclei + Triage v1

Ships the first vulnerability-signal loop:

- `nuclei` runner using only approved template categories
- Expanded `findings` schema
- Finding hash helper and state-machine tests
- Triage engine v1 that reads nuclei and httpx signals and writes `_queue/`

Dependency: 3a.

### 3c - katana + ffuf Signal Sources

Ships the broader active recon surface:

- `katana` runner with depth, duration, and URL caps
- `ffuf` runner with approved wordlists and request caps
- Normalized signal emitters for crawl and content-discovery output
- Triage adapters for katana and ffuf signals (extends the v1 triage contract from 3b)

Dependency: **3a and 3b**. The triage adapters require the triage contract that ships in 3b.

### 3d - Daily Digest, Phone Ping, Freeze-Ack, and Timer Hardening

> **🅿️ Mostly parked on 2026-05-12 after a five-step pass.** Only `bin/ack-freeze` (as a ~10-line shell helper, not the Python module described below) survives. The 08:00 cron digest, phone ping, systemd timer chain, and `ops_runs` audit machinery are all parked with explicit unpark conditions in [`../decisions/2026-05-12-five-step-cut.md`](../decisions/2026-05-12-five-step-cut.md). The original 3d scope is preserved below for future reference.

Ships the operator-facing daily loop:

- `ops/daily-digest.md` generator
- Phone ping via claude-chat bus
- `bin/ack-freeze` CLI (see audit contract below)
- systemd timer + service units in `ops/systemd/` (templates), documented in `ops/scheduling.md`
- Runner health and anomaly reporting
- **Mock-target integration smoke** that exercises the full timer chain (scope-sync → httpx → triage → digest → ping) against a fixture program in a tmp-repo. This proves the chain works without sending any real traffic.
- A separate **operator-approved manual verification pass** against the current scoped program *after* the mock-target smoke passes. The operator runs each timer's service unit manually, in order, with `RECON_ENABLED` armed, and inspects the run trail. No program is hardcoded in source or tests.

Dependency: 3a and 3b. The digest must tolerate missing katana/ffuf runs (3c not yet merged).

#### `bin/ack-freeze` contract

Removing a `FROZEN` flag is a privileged operator action with an audit trail. `bin/ack-freeze <platform>/<slug>`:

1. Refuses to run unless `FROZEN` exists for the named program.
2. Reads and displays the FROZEN content (reason, originating runner, timestamp).
3. Prompts the operator for an acknowledgement message (non-empty, required).
4. Writes an `ops_runs` row with `kind="freeze_ack"`, the original FROZEN content as `payload_digest`, and the operator's message as `error_summary` (despite the name; ops_runs reuses the column for free-form notes).
5. Appends to `programs/<platform>/<slug>/freeze-acks.log` (gitignored) with full content for forensic history.
6. Removes the `FROZEN` flag last, after all the audit writes succeeded.

There is no `--force` flag. There is no auto-removal path. Operators who want to bypass the prompt for scripting must use the lower-level primitive directly and accept that nothing audits that path.

Each sub-phase follows TDD: failing tests first, green implementation, then refactor. Every source file stays under the 200-line cap.

## 7. Open Questions and Explicit Non-Goals

### Open implementation questions

- Confirm the final VPS access path and SSH key before enabling cron.
- Confirm the exact claude-chat bus command or local API available on the VPS.
- Confirm installed tool versions for `httpx`, `nuclei`, `katana`, and `ffuf` before writing parser assumptions.
- Confirm the approved free wordlist subset for ffuf in the 3c plan.
- **Migration atomic boundary.** Does `migrate(conn, target_version)` run each v_n→v_n+1 step in its own committed transaction, or wrap the whole sequence in one transaction? Affects partial-failure recovery (e.g. v2 succeeds, v3 fails). The 3a plan must pick one and write tests for both happy path and crash-after-vN-commit.
- **Signals atomic boundary.** The runner writes both `signals.jsonl` (artifact) and `signals` (table) per batch. One must be authoritative. The 3a plan should pick the DB row as the commit point and treat the JSONL as a write-then-reconcile artifact, with startup logic that rebuilds the JSONL from rows if it's missing or short.
- **Prerequisite freshness, not just ordering.** systemd `After=` orders unit starts, it doesn't gate on prior success. Each downstream runner (nuclei reads httpx, triage reads everything, digest reads triage) must independently query SQLite for a recent successful prerequisite `recon_runs` row before doing work. If the prereq is stale or missing, the runner records a `prereq_missing` anomaly signal and exits cleanly.
- **Mock-target fixture for 3d smoke.** The fixture is a small in-repo HTTP server (e.g. `tests/fixtures/mock_target/`) that serves a deterministic surface: two in-scope hosts, one OOS host, a 302 redirect to OOS (to exercise the wrapper drop), a path with a synthetic nuclei-template hit, a katana-discoverable JS endpoint, an ffuf-discoverable hidden file. The smoke test runs the full timer chain against this fixture and asserts each runner's `recon_runs` row, manifest, and `signals` rows match a recorded snapshot. Detailed in the 3d plan.
- **`bin/ack-freeze` crash-idempotency.** The audit sequence (ops_runs row → freeze-acks.log append → FROZEN unlink) is three writes. The 3d plan should specify an `ack_id` (UUID4) per ack, written first to ops_runs with `status=in_progress`, then status=`success` after the log append, then the FROZEN unlink. A re-run with the same ack_id is a no-op; a re-run after partial completion picks up where the prior run left off based on which writes the `ack_id` has completed.

### Explicit non-goals

- No active recon from the operator laptop.
- No multi-program parallelism. Phase 3 is designed for the current one-program registry and must not hardcode `hackerone/security`.
- No queue-driven scheduler and no pipeline chain where one runner directly starts the next.
- No automated promotion from `_queue/` to `_verified/`.
- No automated submission from `_verified/` to `_submitted/`.
- No mocked findings in `_queue/` or the digest.
- No nuclei templates beyond CVE and standard misconfiguration checks.
- No paid wordlists.
- No social engineering, DoS, destructive payloads, or PII exfiltration.
- No Chaos API repair work. The ProjectDiscovery Chaos 401 issue remains out of scope for Phase 3.
- No report-drafting implementation. Phase 4 owns the verified-to-draft-to-submit loop.
