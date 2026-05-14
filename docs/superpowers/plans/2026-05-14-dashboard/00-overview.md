# 00 — Overview

## Files

Created:
- `src/earn_money/dashboard/__init__.py` (empty package marker)
- `src/earn_money/dashboard/aggregator.py` (~150 lines)
- `src/earn_money/dashboard/server.py` (~100 lines)
- `src/earn_money/dashboard/templates/index.html` (~180 lines, embedded CSS+JS)
- `src/earn_money/registry.py` (~30 lines) — `iter_registered_programs(paths)`
- `bin/dashboard` (sh wrapper, ~15 lines)
- `tests/dashboard/__init__.py` (empty)
- `tests/dashboard/test_aggregator.py` (~140 lines)
- `tests/dashboard/test_server.py` (~60 lines)

Modified:
- `src/earn_money/triage/findings.py` — add `count_findings_by_state(conn, *, platform, slug) -> dict[FindingState, int]` (zero-filled). DAO layer.
- `src/earn_money/triage/queue_cli.py` — promote `_SEVERITY_RANK` and `_sort_key` to a public `triage/severity.py` (or top-level in findings) so the dashboard and the CLI agree on "top queued."

## Status JSON schema (the contract — aggregator → frontend)

```jsonc
{
  "generated_at": "2026-05-14T09:30:00Z",
  "programs": [
    {
      "platform": "hackerone", "slug": "security",
      "policy": "rate-limited-OK",                // Policy Literal
      "last_synced": "2026-05-14T08:00:00Z",
      "frozen": false,
      "frozen_reason": null,                      // populated when frozen=true
      "asset_count": 19, "http_service_count": 15,
      "finding_states": {                         // zero-filled for every FindingState
        "queued": 5, "verified": 1, "submitted": 0,
        "resolved_paid": 0, "resolved_dupe": 0, "resolved_na": 0,
        "resolved_info": 108, "archived": 0
      },
      "top_queue": [                              // ≤ 5; severity DESC then first_seen ASC
        {"hash": "f5df5f0d", "vuln_class": "github-takeover",
         "severity": "high", "asset": "mta-sts.wearehackerone.com",
         "first_seen": "2026-05-14T06:49:52Z"}
      ],
      "recent_runs": [                            // ≤ 20, newest first; UI-needed fields only
        {"tool": "nuclei", "status": "success",
         "started_at": "2026-05-14T02:14:31Z",
         "signal_count": 16, "source_failures": 0}
      ],
      "error": "OperationalError: ..."            // optional; present only when reading the program's DB raised
    }
  ],
  "across": {
    "total_findings": 131,
    "total_queued": 7,
    "suppression_rate_pct": 87.0,                 // resolved_info / (queued+resolved_info)
    "ledger_eur": 0,                              // 0 until ops/ledger.md parser exists
    "first_verified_with_operator_note": false    // generic predicate, no engagement coupling
  }
}
```

## Conventions

- TDD: failing test → run → impl → run → commit.
- ≤200 lines per source file. Split if approached.
- Tests under `tests/dashboard/` mirror `src/earn_money/dashboard/`.
- Server binds 127.0.0.1 only (hardcoded — no `--host` flag).
- Browser polls every **10 s** (changed from 5 s; pipeline state doesn't move faster).
- `/simplify` pass after each commit; `/code-review` if available.

## Anti-goals

- No deltas, ETags, or partial JSON responses. Single user, ~5 KB payload, localhost — full snapshot every poll.
- No TTL cache in the aggregator (revisit if program count > 10).
- No DB indexes added for the dashboard (revisit if any single query > 50 ms).
