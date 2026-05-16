# 11 — Safety, gates, and operational constraints

## Hard rules (must hold in v1)

These are non-negotiable. Failing any of them is a stop-the-world bug.

### 1. `RECON_ENABLED` gate

- `POST /api/probe/start` calls `flags.require_recon_enabled(self._paths)` before doing anything else. If the file is absent, returns `403` with the standard `flags.ReconDisabled` message.
- The kill-switch check runs at *every probe start*, not just at server boot. An operator who deletes `RECON_ENABLED` mid-session can't launch a new probe even though the server is still up.
- A probe already in flight when the file is deleted continues to completion. The kill-switch halts *new* probes; it doesn't terminate running ones (consistent with how every other runner in this repo treats the flag).

### 2. Per-program FROZEN gate

- When the form supplies `program`, `POST /api/probe/start` calls `flags.require_program_not_frozen(self._paths, platform, program)`. On `ProgramFrozen`, returns `403`.
- When `program` is empty (ad-hoc probe against a non-registered URL like `target.cocode.dk` for a local lab), the FROZEN gate is *not* applicable — there's no per-program flag to check.
- **Known limitation** (resolves second-reviewer #8): an operator who *types* the URL of an asset belonging to a frozen registered program — but leaves `program` blank — currently bypasses the FROZEN gate. This matches the CLI's behaviour today (`hacker_loop_cli` also skips FROZEN when `--program` is empty). The clean long-term fix is URL-to-program resolution at gate time; tracked as a follow-up in [13-out-of-scope.md](13-out-of-scope.md) §N. For v1, operators using the dashboard against frozen programs must supply `program` explicitly so the gate fires.

### 3. RoE / scope / budget enforcement is unchanged

- The probe loop runs through the exact same `RoePolicy`, `ScopePolicy`, `RequestBudget`, `HttpTool` chain as `bin/probe-target`. The PROBE tab is an alternate *launcher* — it doesn't alter enforcement.
- Any future change to enforcement (new scope-block rules, new RoE categories, etc.) automatically benefits the PROBE tab; no parallel implementation to keep in sync.

### 4. One active probe at a time

- `_PROBE_SLOT` plus `_PROBE_SLOT_LOCK` (see [06-server-routes.md](06-server-routes.md)). Second start while one is running returns `409 Conflict` with the running probe's `run_id`.
- The slot clears via the `on_finished` callback the server hands to `ProbeRunner` — invoked from the runner's `finally` block regardless of how the loop exits (success, error, operator-cancel). The runner never imports from `server.py`, so there's no circular import.

### 4a. One SSE stream client per probe

- The event queue is a single `queue.Queue` consumed by whichever stream connection drains first. Opening a second SSE stream against the same `run_id` would race with the first — they would steal events from each other, neither one getting a complete sequence.
- **v1 rule**: one stream client per probe. The browser's normal usage (one tab, one `EventSource`) honours this naturally. Refreshing the page during a run drops the prior stream; the operator gets only events that arrive after the refresh — no replay.
- Multi-client support requires a different event-distribution model (in-memory per-client cursors or fan-out via per-connection queues); tracked in [13-out-of-scope.md](13-out-of-scope.md) §B/§C. Resolves second-reviewer #5.

### 4b. Slot cleanup vs. active stream — no race

- When the loop thread reaches `done` (or `probe_error`), the runner's `finally` calls the server's `on_finished` callback, which clears `_PROBE_SLOT`. The *already-connected* SSE handler still holds a direct reference to the runner, so it keeps draining the queue and flushing the final `done` / `probe_error` frame — slot cleanup doesn't yank events out from under it.
- A *new* `GET /api/probe/stream?run_id=…` request issued after cleanup returns `404 no probe running`, because v1 has no event replay. This is the intended behaviour: refresh-after-completion shows an empty PROBE tab, not a half-broken in-progress stream.
- The implication: if the operator alt-tabs during a long probe, the live render persists; if they refresh, they lose it. Documented in [13-out-of-scope.md](13-out-of-scope.md) §B/C.

### 5. `textContent` only — no `innerHTML`

- Every value rendered into the timeline comes from `textContent` or `document.createElement`. Verified by line-by-line review at PR time; the `probe-render.js` file is small enough to audit by eye.
- The `body_excerpt` field in SSE events is the highest-risk surface because it contains literal target output. Treating it as text node content (`.textContent = data.obs.body_excerpt`) neutralises any `<script>` or `<img onerror=…>` payload regardless of source.

### 6. Loopback bind unchanged

- The existing `--host 127.0.0.1` default is preserved. The PROBE tab introduces no new auth path; access control is still "you have shell on the box (or the firewall allow-lists your IP per the existing escape hatch)."
- If the operator binds to `0.0.0.0` via the existing flag, anyone with TCP reach can launch a probe — same exposure as the existing `/api/status` route, no worse.

### 7. No CORS, no preflight, no third-party origins

- The form posts JSON to the same origin. The browser doesn't send a preflight (same-origin, no custom headers beyond `Content-Type: application/json`). The server doesn't emit CORS headers.
- If a future need arises to call `/api/probe/start` from another origin, that's a new design discussion — out of scope here.

## Soft rules (strongly preferred, expect deviations to be argued)

### A. No `eval`, no dynamic script injection in probe.js

- Stay vanilla DOM. If a feature seems to need `eval` or `new Function`, it's almost certainly the wrong feature.

### B. No new Python dependencies

- The existing server is pure stdlib (`http.server`, `json`, `threading`, `queue`, `uuid`, `pathlib`). The probe runner adds nothing — every primitive is stdlib.
- The OpenRouter HTTP path goes through the existing `providers_openai_compat.py` (which already pulls in `openai`); no second SDK.

### C. No new JS bundler / build step

- Three small vanilla files. No npm, no Vite, no TypeScript compilation. The existing `render.js` / `render_panels.js` / `dashboard.js` set this baseline; we match it.

### D. SSE only, no WebSocket

- The wire protocol is one-way (server → client). SSE costs nothing to add over stdlib HTTP and survives long-running idle connections via `:` comment keep-alives.
- WebSocket adds protocol upgrade handling that `BaseHTTPRequestHandler` doesn't support without a third-party library. Not worth it for one-way streaming.

## What happens on each failure mode (operator-visible)

| Failure                        | Server response               | Client display                  |
|--------------------------------|-------------------------------|---------------------------------|
| `RECON_ENABLED` absent         | 403 + flags message           | Error banner: gate              |
| Program FROZEN                 | 403 + flags message           | Error banner: gate              |
| Another probe running          | 409 + existing run_id         | Error banner: conflict          |
| Bad JSON body                  | 400                           | Error banner: validation        |
| RoE profile path invalid       | 400 + `RoE profile not found: <path>` | Error banner: gate      |
| Provider misconfigured at runner init | 500 + `runner init failed: <msg>`   | Error banner: gate       |
| Provider fails during an LLM call     | 200 + `probe_error` event (mid-stream) or `done(stop_reason=llm_error)` | Error/finished banner |
| LLM returns garbage repeatedly | 200 + `done` (invalid_action) | `done` banner with stop_reason  |
| Loop crashes mid-turn          | 200 + `probe_error` event     | Error banner mid-stream         |
| Operator clicks RUN twice fast | second click is no-op         | (button disabled while running) |
| Operator closes the tab        | server keeps running          | (loop continues to completion)  |

The last row is intentional: a closed browser tab doesn't cancel the probe. Operator can reopen the dashboard, hit RUN with the same form values, and either (a) see the running probe via the 409 + `run_id` (and could `GET /api/probe/stream` to re-attach) or (b) wait for the running probe to finish and start a new one. **Re-attach is not implemented in v1** — the SSE stream replays nothing; the operator sees only events that arrive after they connect. Listed as a follow-up in [13-out-of-scope.md](13-out-of-scope.md).

## Auditability

- Each probe run gets a `run_id` (uuid4 hex). The same id appears in the server log, the SSE stream, the `done` event, and (future) any persisted history.
- `log.info` in the probe runner stamps every emitted event with `run_id`, `turn`, `event_name`. Operators reading the server's stderr can correlate UI events with backend state.
- No findings are persisted from the PROBE tab in v1 — the timeline is ephemeral. Findings worth saving still go through the CLI (`bin/probe-target`) which writes to the program's SQLite. The dashboard is for *watching*, the CLI is for *recording*.

## What this spec does NOT relax

- **Two human gates** (`findings/_queue/ → _verified/` and `_verified/ → _submitted/`) — completely untouched. The PROBE tab can produce candidates and (rarely, via the verifier) verified findings, but those are visible only in the live timeline. Nothing in this spec moves a finding from one gate to the next.
- **Three-tier program policy** — when `program` is supplied, the same `policy:` declaration in `scope.md` governs whether the probe is allowed to run. The `ScopePolicy` constructed inside the runner reads it.
- **GDPR / PII handling** — the `roe.md` invariants (`pii_handling: synthetic_data_only`, etc.) apply to the threaded loop exactly as they do to the CLI loop. No new PII surface introduced.

## Review history

This file resolves the cursor-agent review concerns:
- #4 (`stop()` semantics) — see [05-probe-runner.md](05-probe-runner.md) §"Thread lifecycle" and §"Internals".
- #6 (EventSource auto-reconnect) — `retry: 0` in the SSE response, `closed` flag in `probe.js`, both described above and in [06-server-routes.md](06-server-routes.md), [09-frontend-probe-client.md](09-frontend-probe-client.md).
- The `RECON_ENABLED` + `FROZEN` integration is consistent with the gate work landed in the LLM-LOOP branch (`feat/run-target-script`).
