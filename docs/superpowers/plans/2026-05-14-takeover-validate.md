# Subdomain-Takeover Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Validate dangling-CNAME takeover candidates against known SaaS-provider fingerprints. Nuclei flags `http/takeovers` template matches but doesn't *verify* control; subzy does. Output goes into the existing `signals → findings/_queue` pipeline. The highest-payout finding class for *.algolianet.com.

**Architecture:** New active-recon runner parallel to `nuclei_scan`. Reads in-scope assets, hands them to subzy in batches, parses JSON output, filters by scope, inserts Signals. Consults `roe.md` for rate cap, embeds the loaded RoE in `manifest.json` for audit. Refuses to start without recent httpx run (same prereq freshness check as nuclei).

**Tech Stack:** Python 3.12, the existing `recon/`, `runners/`, `signals` modules. New binary dependency: `subzy` (Go-based, installed via `go install github.com/PentestPad/subzy@latest`).

---

## Anti-goals (do NOT do)

- No automatic claim-the-CNAME action. Subzy *detects* takeover potential; the operator decides whether to claim the dangling target as PoC (manual, scope-gated step).
- No nuclei replacement. Subzy complements nuclei's `http/takeovers` template — different fingerprint set, different verification depth. Both keep running.
- No fingerprint database in this repo. Subzy ships its own; we don't curate provider patterns.

## File structure

| Path | Responsibility |
|------|----------------|
| `src/earn_money/recon/subzy_tool.py` (new) | `build_command(targets, *, rate_limit)`, `parse_jsonl(raw, run_id, observed_at)`, `SubzyUnavailable` |
| `src/earn_money/runners/takeover_validate.py` (new) | `run_program(paths, platform, slug, *, tool_run, run_id, max_targets)` — same shape as `nuclei_scan.run_program` |
| `src/earn_money/runners/takeover_validate_cli.py` (new) | CLI entry-point + real-tool wiring, catches `InvalidRoE → exit 6`, `UnsafeTemplateProfile` analogue not needed |
| `bin/takeover-validate` (new) | Thin Python wrapper, same shape as `bin/nuclei-scan` |
| `tests/recon/test_subzy_tool.py` (new) | `build_command` + `parse_jsonl` with fixture |
| `tests/runners/test_takeover_validate.py` (new) | Gate refusal, scope filtering, signal insertion, manifest embeds RoE |
| `tests/fixtures/subzy_output.json` (new) | Representative subzy output: 2 VULNERABLE, 1 NOT_VULNERABLE, 1 HTTP_ERROR |
| `scripts/install-vps.sh` (mod) | Add `go install github.com/PentestPad/subzy@latest` to the tooling block |

---

## Subzy output schema (target)

Subzy emits a JSON array with one entry per target:

```json
[
  {"data": "mta-sts.example.com", "status": "VULNERABLE",     "service": "Heroku",       "vulnerable": true,  "https_status": 404},
  {"data": "www.example.com",      "status": "NOT_VULNERABLE", "service": null,          "vulnerable": false, "https_status": 200},
  {"data": "old.example.com",      "status": "HTTP_ERROR",     "service": null,          "vulnerable": false, "https_status": 0}
]
```

Parser keeps only `vulnerable: true` entries. Signal signature: `subzy|<service>|<cname>` (lowercased). Asset = `data`. Target = `https://<data>/`. Severity hint: `high` (most subdomain-takeover findings are P1/P2 on H1).

---

## Task 1: subzy_tool wrapper (TDD)

**Files:** create `src/earn_money/recon/subzy_tool.py`, `tests/recon/test_subzy_tool.py`, `tests/fixtures/subzy_output.json`.

- [ ] **Step 1.1: Write the fixture.** Three entries as shown above, one each: vulnerable, not vulnerable, http_error.
- [ ] **Step 1.2: Write failing tests.** Cover:
  - `build_command` includes `-targets <tmpfile>` and `-output -` (stdout) and `-hide_fails` flag
  - `build_command` includes `-concurrency <rate_limit>` from the kwarg
  - `build_command` requires at least one target
  - `parse_jsonl` returns one Signal for the VULNERABLE row only
  - The returned signal has `signal_type="takeover_vulnerable"`, severity hint in payload, signature matches `subzy|heroku|...`
  - `parse_jsonl` tolerates malformed top-level (returns empty list rather than crashing)
- [ ] **Step 1.3: Implement** following the `nuclei_tool.py` shape — pure functions, no subprocess. Hash signals via `triage.hashing`.
- [ ] **Step 1.4: smoke** (`make smoke`).
- [ ] **Step 1.5: commit** `feat(subzy): tool wrapper + JSON parser for takeover signals`.

## Task 2: takeover_validate runner (TDD)

**Files:** create `src/earn_money/runners/takeover_validate.py`, `tests/runners/test_takeover_validate.py`.

- [ ] **Step 2.1: Write failing tests.** Cover (mirror the existing nuclei_scan resilience tests):
  - Refuses without `RECON_ENABLED`
  - Refuses with policy `manual-only`
  - Refuses without recent successful httpx run
  - Loads in-scope assets with explicit-first sort
  - Respects `max_targets`
  - Filters signals by `is_in_scope(sig.asset, …)`
  - Writes manifest with the `roe` block (`program_roe.manifest_payload()`)
  - Records `recon_runs` row with `tool='subzy'`
- [ ] **Step 2.2: Implement.** Same shape as `nuclei_scan.run_program`. Read assets from `assets` table (subdomains) not `http_services` — subzy needs the bare hostname.
- [ ] **Step 2.3: smoke + commit** `feat(takeover): subzy-based dangling-CNAME validator runner`.

## Task 3: takeover_validate CLI + bin wrapper

**Files:** create `src/earn_money/runners/takeover_validate_cli.py`, `bin/takeover-validate`.

- [ ] **Step 3.1: Implement** following `nuclei_scan_cli.py` exactly — argparse for `--platform/--program/--root/--max-targets`, named exit codes (2/3/4/6), `resolve_rate_limit` reused via import (or its own helper).
- [ ] **Step 3.2: Test** the CLI exits 6 on invalid roe.md (same pattern as nuclei).
- [ ] **Step 3.3: bin/takeover-validate** = 5-line wrapper that calls `takeover_validate_cli.main()`. chmod +x.
- [ ] **Step 3.4: smoke + commit** `feat(takeover): CLI entry point + bin wrapper`.

## Task 4: VPS installer wires subzy

**Files:** modify `scripts/install-vps.sh`.

- [ ] **Step 4.1:** Add `go install -v github.com/PentestPad/subzy@latest` to the tooling block, sanity-check the binary lands on PATH (`subzy --version` returns 0).
- [ ] **Step 4.2: commit** `chore(install-vps): install subzy for takeover validation`.

## Task 5: /simplify + /code-review

- [ ] **Step 5.1: Run /simplify** against branch diff. Apply findings.
- [ ] **Step 5.2: Run feature-dev:code-reviewer** against branch. Apply findings.
- [ ] **Step 5.3: smoke + final commit if needed.**

## Task 6: PR + merge + sync

- [ ] **Step 6.1: push branch.**
- [ ] **Step 6.2: open PR via `gh pr create`.**
- [ ] **Step 6.3: surface to operator** for review. Merge once approved.
- [ ] **Step 6.4: sync VPS with `scripts/sync-vps.sh`** + re-run `install-vps.sh` to bring subzy on board.
