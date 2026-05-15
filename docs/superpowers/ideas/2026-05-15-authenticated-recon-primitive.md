# Authenticated-recon primitive

> Research note 2026-05-15. Not yet brainstormed into a spec. Prerequisite for several Phase 6 plugin ideas.

## What

A shared HTTP-client substrate for authenticated probing: cookie jar persisted per program-and-handle, automatic token refresh / re-login on 401, identity-pair support (two test accounts so one can probe the other's resources). Sits below the active-runner layer so any plugin can opt into authenticated traffic without re-implementing session management.

## Why

The disclosure-replay first pass quantified this: across the 21-row corpus, **17 rows scored as 16 FN + 1 inconclusive** (4 algolia historical anchors excluded). Among those, `requires-auth` is the dominant hint — 3 of the 6 Info-Disclosure rows across the portfolio are `requires-auth` (the other 3 are `requires-business-logic`, `requires-payload-crafting`, and `regex-friendly`). All the plugin ideas below except `apk-endpoint-extractor` need authenticated traffic to fire on real disclosed patterns; `upload-memory-probe` is soft-dependent on auth (most worthwhile upload endpoints are auth-gated). This primitive is the infrastructure investment that unlocks the rest.

## Shape (sketch)

- `src/earn_money/recon/auth.py` — `AuthenticatedClient(program, identity_handle)` wrapping httpx. Loads credentials from an out-of-repo store: `identity/platforms.md` is already gitignored, but `identity/test-accounts.<program>.json` is NOT — add it to `.gitignore` (or store fully out-of-repo / encrypted) before any code lands. Pre-commit hook + a tracked-files check in the runner are reasonable belt-and-suspenders.
- Token refresh hook: configurable per program — most use a `/login` form-post or OAuth refresh; some use API keys.
- Two-identity mode: `IdentityPair(a, b)` yields two configured clients for cross-account probing.
- Rate-limit shared with the runner's RoE-derived `max_requests_per_second`.

## Effort

Meaningful — probably 2-3 days of TDD. Three sub-pieces: client wrapper, identity store, refresh contract. Best landed as its own brainstorm-spec loop before any plugin consumes it.

## Hard rules carried in

- `scope.md` policy gating is unchanged: `manual-only` refuses any runner, `ambiguous` allows passive-only, `rate-limited-OK` permits full pipeline. Authenticated probing is "active" recon and follows the same tier rules.
- `roe.md` continues to govern technique authority + rate cap. The auth-recon primitive consumes the existing `max_requests_per_second` field — no separate dial.
- Asset gating: any authenticated request must be against an asset in the program's current `in_scope` list. Out-of-scope assets that happen to share the auth domain are off-limits.
- Kill-switch + freeze flags: `RECON_ENABLED` and per-program `FROZEN` checks apply identically. The auth wrapper checks both on every probe.
- "One handle per platform" still holds. Test accounts authenticated against the program are operator-owned credentials under the same researcher handle, never sock-puppets.
- Where `roe.md` declares `pii_handling: synthetic_data_only`, authenticated probing must use program-provided synthetic accounts. Real-user impersonation is out.

## Prior art / disclosures it would have enabled

Every `requires-auth` row across the corpus — **4 on bykea** (`/reports/2209750` Info-Disclosure, `/reports/2374730` IDOR, `/reports/2867022` Auth-Bypass, `/reports/3085742` IDOR), multiple on h1-security (the 2 IDOR + 2 of the 4 Info-Disclosure rows), and the algolia historical Auth-Bypass (`/reports/1276373`) which is requires-chain but auth-rooted. The plugin work below stacks on top.
