# Plugin idea: `idor-probe`

> Research note 2026-05-15. Pre-brainstorm.

## What

Authenticated multi-account IDOR detector. Given two test accounts logged in via the authenticated-recon primitive, walk known endpoints, mutate object IDs from account B into account A's requests, diff responses against the baseline "A sees A's data" call. Flag any case where account A's session returns B's data (or successfully mutates B's resource).

## Why

IDOR is the **single most universal vuln class** across the corpus — **4 FN rows on bykea + security** (2 each). Algolia's historical corpus has no IDOR row specifically; the architecturally-adjacent algolia historical is `/reports/1276373` Auth-Bypass, which the mutation variant of this plugin may also surface. Zero current plugins target IDOR directly. The disclosed reports demonstrate the exact pattern: numeric/sequential object IDs, cross-account substitution, predictable mutation endpoints.

## Disclosed prior art

- `hackerone/reports/2374730` — Bykea booking_id IDOR (GET on `/api/v1/bookings/{id}` reads other users)
- `hackerone/reports/2867022` — Bykea trip hijacking (`/acknowledged_the_offer`, `/accept` don't validate trip_id ownership — body substitution)
- `hackerone/reports/3085742` — Bykea Android zombie endpoint IDOR (iterable object ID; surface from APK static analysis)
- `hackerone/reports/2894018` — Bykea cross-trip feedback (POST accepts trip_id + driver_id without cross-validation)
- Multiple h1-security IDOR rows (program-private detail)

## Shape (sketch)

- Input: endpoint list (from the active-pipeline's discovered URLs, plus the `apk-endpoint-extractor` output), endpoint catalogue annotated with object-ID parameter positions.
- For each endpoint with an object-ID slot: client A fetches with A's IDs (baseline), then with B's IDs (probe). Compare body / status / response-time. Heuristics: success-when-expecting-403, content overlap with B's known data, response size delta.
- Mutation variant: same but on POST/PUT/PATCH endpoints — verify whether B's resource was actually changed. **Mutation probing is destructive** and is opt-in per program: only fire on disposable operator-owned or program-provided synthetic resources (e.g. an account explicitly designated for destructive testing in `roe.md`'s `authorized_test_accounts`). Never mutate a third-party resource even when an IDOR is detected; the read-variant is sufficient to file the report.
- Every mutation attempted must be tracked for cleanup; the plugin maintains a per-run rollback log so the operator can restore state if the program's auto-rollback misses.
- Output rows into the `signals` table with `signal_type='idor_candidate'`, then triage promotes per the existing engine.

## Effort

Medium — depends entirely on the authenticated-recon primitive existing first. Once that's in, the IDOR logic itself is a few hundred lines + tests. Probably 2-3 days net.

## Prerequisites

[[2026-05-15-authenticated-recon-primitive]] is hard-blocking. Endpoint catalogue from [[2026-05-15-plugin-apk-endpoint-extractor]] is force-multiplier but not required (could start from active-pipeline's discovered URLs).

## Hard rules

- Two test accounts both operator-owned, both under the same researcher handle (no sock-puppets).
- Policy tier comes from `scope.md`, not `roe.md`. Only `rate-limited-OK` programs run this plugin — `manual-only` refuses all runners; `ambiguous` permits passive-only and active-IDOR is not passive. `roe.md` then governs the rate cap and any technique-level extras the program authorises.
- PII handling: probing must use operator-owned synthetic accounts or program-provided test accounts. If real third-party PII appears anyway (e.g. an IDOR returns a real customer's record despite a synthetic probe), STOP, retain one redacted-screenshot of evidence per CLAUDE.md, do not store the raw response, and surface to the operator immediately.

## Estimated catch rate against current corpus

**2 direct + up to 2 adjacent** on Bykea: `/reports/2374730` and `/reports/3085742` are IDOR direct (read-substitution). `/reports/2867022` (Auth-Bypass) and `/reports/2894018` (Logic-Flaw cross-trip feedback) are adjacent — same architectural shape (cross-account ID substitution on mutation), catchable only if the plugin's mutation variant is enabled and the endpoints' parameter positions are known. Plus the algolia historical Auth-Bypass and 2 IDOR rows on h1-security. **Largest single FN-coverage plugin in the candidate set, but cursor-correctly: not 4-of-8 on direct semantics alone.**
