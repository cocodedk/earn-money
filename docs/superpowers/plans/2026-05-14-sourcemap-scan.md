# Sourcemap / JS-Bundle Analyzer Plan

> **For agentic workers:** Use superpowers:executing-plans. Checkbox steps.

**Goal:** Passively mine front-end JS bundles for high-value leaks: exposed `.js.map` files, hardcoded AWS keys, GitHub PATs, JWT secrets, and back-end endpoint manifests. The marketing-site / dashboard JS is where ops mistakes hide.

**Architecture:** Pure-function tool (`sourcemap_tool.py`) + active-mode runner (`sourcemap_scan.py`) + CLI. Tool layer fetches HTML, extracts `<script src=>` URLs, downloads each JS, finds sourcemap comments, downloads the `.js.map`, runs regex secret-finders over both. Runner enforces scope + RoE rate cap. Same shape as nuclei/takeover runners. No new external binaries — `httpx` lib already in deps.

## Anti-goals

- No deobfuscation. Subset of `.js.map` files we fetch are minified-map sources; raw regex against the text is sufficient for high-value leaks. Anything more sophisticated belongs in a later runner.
- No fuzzing or path discovery. We fetch only what the HTML links to.
- No exploitation. A detected secret is a Signal; the operator verifies + reports.

## File structure

| Path | Lines | Purpose |
|------|-------|---------|
| `src/earn_money/recon/secret_patterns.py` (new) | ~80 | Regex catalogue + `find_secrets(text)` |
| `src/earn_money/recon/sourcemap_tool.py` (new) | ~150 | HTML parser, sourcemap fetcher, signal builder |
| `src/earn_money/runners/sourcemap_scan.py` (new) | ~150 | Runner: gate → load assets → fetch → scope-filter → record |
| `src/earn_money/runners/sourcemap_scan_cli.py` (new) | ~120 | CLI entry, exit ladder |
| `bin/sourcemap-scan` (new) | 17 | Shell wrapper |
| `tests/recon/test_secret_patterns.py` | ~100 | Per-pattern positive + negative cases |
| `tests/recon/test_sourcemap_tool.py` | ~120 | Bundle-URL extraction, sourcemap-comment parsing |
| `tests/runners/test_sourcemap_scan.py` | ~150 | Gate refusal, scope filter, signal insertion, RoE manifest |
| `tests/fixtures/sourcemap_*.html` / `.js` / `.js.map` | small | Representative inputs |

## Signal shape

`tool="sourcemap-scan"`, `signal_type ∈ {"exposed_sourcemap", "leaked_secret"}`. Severity hint by pattern:

- AWS access key / GitHub PAT / Slack token → **high**
- JWT (decodable, alg ≠ none) → **medium**
- Exposed `.js.map` (200 response, valid JSON) → **info**
- Generic `api_key = "..."` literal → **unknown** (filtered by existing triage rules)

## Tasks

1. **Secret patterns module + tests** (TDD, ~80 + ~100 lines)
2. **Sourcemap tool module + tests** (HTML extraction, sourcemap comment parser, secret-finder integration; mock HTTP via `httpx.MockTransport`)
3. **Runner + tests** (scope/policy/RoE gates; calls injected fetcher)
4. **CLI + bin wrapper** (exit codes 2/3/4/6, mirrors takeover_validate_cli)
5. **/simplify + /code-review** until clean
6. **PR + merge + sync**

## Scope-safety invariant

Only fetch URLs whose host is `is_in_scope(host, in_scope, out_of_scope)`. Cross-origin `<script src=>` (e.g. `cdn.amplitude.com`) is *skipped*, not fetched. This is enforced in the runner before any HTTP traffic leaves the box.
