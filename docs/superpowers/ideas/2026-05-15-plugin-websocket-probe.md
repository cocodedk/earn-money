# Plugin idea: `websocket-probe`

> Research note 2026-05-15. Pre-brainstorm.

## What

Connect to authenticated WebSocket endpoints, observe the message stream as a passive listener, and flag fields appearing before their "authorized state." Distinct from HTTP probes in that the channel is push-based and the leak is temporal (a field appears in a message frame at a state when it shouldn't yet be visible).

## Why

Real-time dashboards / ride-hailing / collaboration tools all push data over WebSockets that REST scanners can't see. One Bykea disclosure was exactly this shape: driver sockets received `trip_no` *before* bid acceptance, and `trip_no` fed customer tracking URLs that leaked rider PII. The disclosed vector summary in `benchmarks/disclosures/hackerone-bykea.json` describes the WebSocket leak directly; it does not claim the HTTP API was the correctly-redacting baseline (earlier draft of this note overstated that — corrected). The WS push channel is the documented vulnerable surface.

## Disclosed prior art

- `hackerone/reports/2209750` — Bykea WebSocket leak (`trip_no` in driver sockets pre-acceptance → customer-tracking-URL → rider PII).

## Shape (sketch)

- Discovery: httpx already records `Upgrade: websocket` and 101-status responses; enumerate WS endpoint candidates from that.
- Authenticated WS client (built on the recon primitive's cookie/header pass-through). Connect, observe frames for N seconds while a second client triggers known state transitions (acceptances, cancellations, status changes).
- Heuristic: build a per-state expected-field schema from observed frames in steady-state; flag any field that appears in a frame BEFORE its authorized state-transition.
- Signal: `websocket_field_leak_candidate` with the channel, frame, and field name.

## Effort

Medium — depends on the authenticated primitive existing. Once that's in, WS-specific work is ~200-400 lines. Maybe **2 days of TDD**. The harder part is the per-program state-transition trigger script (needs to know "what action moves the trip from `offered` to `accepted`"), which overlaps with [[2026-05-15-plugin-state-machine-fuzzer]]'s per-program model.

## Prerequisites

- [[2026-05-15-authenticated-recon-primitive]] — hard-blocking.
- Per-program transition map — partial; can start with manual trigger scripts.

## Hard rules

- Policy tier from `scope.md`: `rate-limited-OK` only. WS probing with state-transition triggers is active recon.
- Same per-program rate-cap binding from `roe.md` — many programs treat WS frames the same as HTTP requests for the cap.
- **Synthetic flows required up front.** Use operator-owned synthetic accounts (rider + driver test pair on Bykea) or program-provided test accounts listed in `roe.md`'s `authorized_test_accounts`. Do not connect with credentials that produce real-user traffic on the channel.
- **Never archive raw WS streams.** Stream observation is in-memory only; the plugin emits structured signal rows (channel + field name + state context) but does NOT persist the frame bodies. If a leak fires on real third-party PII anyway, stop the run, retain one redacted screenshot of the offending frame per CLAUDE.md, surface to operator.

## Estimated value-add

Narrow but specific — 1 of 8 Bykea disclosures (cited at medium severity per the corpus, not critical — earlier draft overstated this), and likely 0-2 across other programs depending on their architecture. The reusable value is the WS-aware capability itself: most programs that ever produce WS-leak findings will repeat the pattern on adjacent channels, so a working WS probe is high-leverage per-program once it fires. Build after `idor-probe` lands and the authenticated primitive is mature.
