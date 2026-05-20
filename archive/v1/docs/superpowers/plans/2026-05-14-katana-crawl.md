# Katana Crawler Plan

> **For agentic workers:** Use superpowers:executing-plans. Checkbox steps.

**Goal:** Surface routes that nuclei + httpx don't see — admin pages, beta features, internal API prefixes — by crawling in-scope HTTP services with ProjectDiscovery's `katana`. Output is a JSONL artifact per run; operators choose which routes to fuzz further. **Not** wired into the auto-promote pipeline yet (no Signals from this v1).

**Architecture:** Same shape as nuclei: tool wrapper (`katana_tool.py`) + runner (`katana_crawl.py`) + CLI. Calls `katana -jsonl -no-color -depth N -concurrency C` against in-scope service URLs, captures stdout, parses, scope-filters the discovered URLs, writes `discovered_urls.jsonl` artifact. No DB writes — discovered URLs land on disk only for now (avoids polluting `signals` with info-class noise).

## Anti-goals

- No automatic re-feed of discovered URLs into nuclei. v2.
- No JS-rendered crawl (`-jc`) — too slow + adds Chrome dependency. v2.
- No POST / form-submit crawl. Bounty programs typically don't authorize state mutation from a crawler.

## File structure

| Path | ~Lines | Purpose |
|------|--------|---------|
| `src/earn_money/recon/katana_tool.py` (new) | 130 | `build_command` + `parse_jsonl(raw, in_scope)` → list of `DiscoveredUrl` |
| `src/earn_money/runners/katana_crawl.py` (new) | 170 | Runner: gate → load services → run katana → scope-filter → write artifact |
| `src/earn_money/runners/katana_crawl_cli.py` (new) | 150 | CLI entry, exit ladder, batch wiring with watchdog |
| `bin/katana-crawl` (new) | 17 | Shell wrapper |
| `tests/recon/test_katana_tool.py` | 90 | `build_command` + JSONL parser fixture |
| `tests/runners/test_katana_crawl.py` | 130 | Gate refusal, scope filter, artifact write, manifest RoE |
| `tests/fixtures/katana_output.jsonl` | small | 3 lines: 2 in-scope, 1 OOS |

## RoE wiring

`max_requests_per_second` → katana `-rl` (it has a real per-second rate cap, unlike subzy). Embeds in manifest like other runners.

## Scope safety

Katana follows links it discovers. Each emitted URL is re-checked against the *live* scope before persisting — even though `-cs` is set to the in-scope hosts, katana can still report cross-host link-followers and we want zero traffic-leakage on persisted URLs.

## Tasks

1. Tool wrapper + parser tests
2. Runner + tests (mock tool_run)
3. CLI + bin + scope-aware command_factory
4. `install-vps.sh` re-check (katana listed but missing on VPS — re-run install loop)
5. /simplify + /code-review
6. PR + merge + sync + ensure katana installs
