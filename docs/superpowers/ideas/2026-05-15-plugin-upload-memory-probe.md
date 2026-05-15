# Plugin idea: `upload-memory-probe`

> Research note 2026-05-15. Pre-brainstorm.

## What

Probe for file-upload endpoints that leak server memory into the stored file. Upload various file shapes/sizes (well-formed, near-empty, oversized, fragmented), fetch the stored copy back, and inspect for non-content bytes that suggest the server appended memory chunks during the buffering stage.

## Why

Narrow but specific class of bug — and one disclosed against Bykea directly. The pattern (server buffers uploaded chunks to local disk before S3, misconfigured ring buffer appends server memory) is uncommon but high-impact: leaks credentials, session tokens, other users' data straight into a file the attacker downloads back.

## Disclosed prior art

- `hackerone/reports/3228011` — Bykea `/talos/api/v1/files/upload` returned server memory chunks appended to uploaded files (Critical severity — one of two Criticals in Bykea's 8; the other is `/reports/2867022` Auth-Bypass which this plugin doesn't address). The disclosed exploit was payload-crafting: vary upload size to trigger the off-by-one in the buffering code.

## Shape (sketch)

- Input: file-upload endpoints from the discovered URL set (httpx tagged `multipart/form-data` accepting or `Content-Type: application/octet-stream` POSTs).
- For each: upload a controlled payload (e.g. 4 KB of `A`s, then 8 KB, then odd sizes near common page boundaries 4096 / 8192 / 16384), then GET back via the documented retrieval flow.
- Heuristic: scan returned bytes for ASCII strings not in the upload (`grep -aE '[!-~]{8,}'`), non-zero entropy in regions that should be all-`A`s, presence of known sentinels (`Bearer `, `session`, common HTTP header keys).
- Signal: `signal_type='upload_memory_leak_candidate'` with the offending file URL + the suspicious byte range.

## Effort

Low — once you have an authenticated upload pathway, the probe itself is ~100 lines. The auth pathway is the lift.

## Prerequisites

Most file-upload endpoints worth probing are authenticated. Soft-blocked on [[2026-05-15-authenticated-recon-primitive]] unless the program exposes anonymous upload.

## Hard rules

- Upload payloads are inert (just `A`s and known sentinels). No exploit chains, no executables, no shell payloads.
- Files uploaded are deleted via the application's own delete flow if it exists; otherwise reported in the disclosure for cleanup.
- **PII / secret handling on detection**: returned bytes may contain other users' credentials, session tokens, raw memory pages. The plugin MUST NOT archive the raw returned file. Store only: byte-range offsets where suspicious content was detected, a one-line entropy/sentinel summary, and (per CLAUDE.md) at most one redacted screenshot for evidence. Stop probing this endpoint after the first credible leak — escalating leak count doesn't strengthen the report, it just multiplies PII exposure.
- Per-program rate cap binds. At 1 req/s a 100-upload probe is **≥ ~200 seconds in practice** (each "round" is upload + GET-back + optional DELETE = 2–3 requests). Budget accordingly.
- Policy tier from `scope.md`: `rate-limited-OK` only. `manual-only` and `ambiguous` refuse this plugin (uploads are active recon, not passive).

## Estimated value-add

Narrow — would catch the one Bykea Critical and not much else in the corpus. But the disclosed value is high (1 Critical in 8 disclosures = ~12% of severity-weighted FN volume on Bykea). Cheap enough to be worth carrying as a one-shot per file-upload endpoint.
