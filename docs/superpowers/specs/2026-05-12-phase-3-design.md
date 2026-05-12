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

Long-running runners also re-check the master switch and freeze flag before each batch. The shared result shape includes `run_id`, `targets_considered`, `targets_scanned`, `artifacts_written`, `signals_emitted`, and `source_failures`.

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
- A `phone_ping_sent_at` field in the digest runner result or manifest

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

### `assets` additions

Existing columns stay in place. Phase 3 may widen how `ports` and `fingerprint` are populated:

- `ports` stores a comma-separated list of observed HTTP(S) ports.
- `fingerprint` stores compact JSON with the latest httpx fingerprint summary.

No new `assets` columns are required for Phase 3a unless implementation shows the compact JSON is too awkward.

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
- `triaged_at TEXT`
- `error_summary TEXT`

Allowed `status` values:

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

### Finding hash composition

`finding_hash` is `sha256` over this canonical string:

```
v1|<platform>|<slug>|<vuln_class>|<normalized_asset>|<normalized_target>|<signature>
```

The hash does not include run ID, timestamps, evidence path, title, or severity. Those can change without creating a duplicate candidate.

Examples of `signature`:

- nuclei: `<template_id>|<matcher_name>`
- httpx anomaly: `<signal_type>|<old_fingerprint>|<new_fingerprint>`
- katana: `<endpoint_shape>|<sorted_parameter_names>`
- ffuf: `<path>|<status>|<response_length_bucket>|<content_type>`

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

## 5. Cron Schedule

Cron runs on the VPS only. Development on the operator laptop is limited to tests, dry runs with mocked tools, and code review.

| Job | Cron | Time zone | Cadence | Rationale |
| --- | --- | --- | --- | --- |
| Scope sync | `0 * * * *` | UTC | Hourly | Scope is the safety boundary. Fast freeze beats stale target lists. |
| Passive recon | `10 */6 * * *` | UTC | Every 6 hours | Asset churn is useful, but passive sources are cheap and low friction. |
| httpx probe | `35 */6 * * *` | UTC | Every 6 hours | Liveness and fingerprints change more often than deeper findings. Keep this light and frequent. |
| nuclei scan | `15 2 * * *` | UTC | Daily | Standard CVE and misconfig checks are useful daily, but should stay inside the off-peak active window. |
| katana crawl | `15 3 */2 * *` | UTC | Every 2 days | Endpoint discovery changes slower than liveness and creates more traffic. |
| ffuf scan | `20 4 * * 0` | UTC | Weekly | Content fuzzing is the highest-friction unit, so it starts weekly with small approved lists. |
| Triage | `30 5 * * *` | UTC | Daily | Correlates all untriaged runs after the active window and before the digest. |
| Daily digest | `0 8 * * *` | Europe/Copenhagen | Daily | Matches the operator's daily work slot. |
| Phone ping | `5 8 * * *` | Europe/Copenhagen | Daily | Runs after the digest exists and sends only a short notification. |

All active runners also support manual invocation on the VPS for incident response or implementation verification. Manual active invocation still checks `RECON_ENABLED`, freeze flags, scope, and policy.

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
- Triage adapters for katana and ffuf signals

Dependency: 3a. It integrates with the triage contract from 3b.

### 3d - Daily Digest, Phone Ping, and Cron Hardening

Ships the operator-facing daily loop:

- `ops/daily-digest.md` generator
- Phone ping via claude-chat bus
- Cron table documentation in `ops/cron.md`
- Runner health and anomaly reporting
- End-to-end smoke test on the VPS against `hackerone/security`

Dependency: 3a and 3b. It should include 3c data when 3c is already merged, but the digest generator must tolerate missing katana or ffuf runs.

Each sub-phase follows TDD: failing tests first, green implementation, then refactor. Every source file stays under the 200-line cap.

## 7. Open Questions and Explicit Non-Goals

### Open implementation questions

- Confirm the final VPS access path and SSH key before enabling cron.
- Confirm the exact claude-chat bus command or local API available on the VPS.
- Confirm installed tool versions for `httpx`, `nuclei`, `katana`, and `ffuf` before writing parser assumptions.
- Confirm the approved free wordlist subset for ffuf in the 3c plan.

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
