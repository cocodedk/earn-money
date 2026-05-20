# 01 — Architecture

## Block diagram

```
┌────────────────────────────────────────────────────────────────────────┐
│  Browser                                                               │
│  ┌────────────────────────┐    ┌──────────────────────────────────┐    │
│  │  RECON tab (existing)  │    │  PROBE tab (new)                 │    │
│  │  polls /api/status     │    │  form ── POST /api/probe/start ──┼─┐  │
│  │                        │    │  EventSource("/api/probe/stream  │ │  │
│  │                        │    │              ?run_id=…")         │ │  │
│  └────────────────────────┘    └──────────────────────────────────┘ │  │
└────────────────────────────────────────────────────────────────────┼──┘
                                                                     │
┌────────────────────────────────────────────────────────────────────▼──┐
│  Dashboard server (stdlib ThreadingHTTPServer)                        │
│                                                                       │
│   _PROBE_SLOT: ProbeRunner | None    ← module-level, one at a time    │
│                                                                       │
│   POST /api/probe/start ──► RECON_ENABLED + FROZEN gates              │
│                          ── ProbeRunner(base_url, …).start()          │
│                          ── returns {run_id}                          │
│                                                                       │
│   GET  /api/probe/stream ─► drains ProbeRunner.events()               │
│                          ── frames as `event: <name>\ndata: <json>\n\n` │
│                          ── closes after done / probe_error          │
└──────────────────────────────────────┬────────────────────────────────┘
                                       │
                          ┌────────────▼────────────┐
                          │  ProbeRunner (thread)   │
                          │  subclass of HackerLoop │
                          │                         │
                          │  overrides:             │
                          │  _get_llm_response()    │   pick task per turn
                          │  _on_llm_response()     │   ─► queue: turn(action_pending)
                          │  _on_action_parsed()    │   ─► queue: turn(action_parsed)
                          │  _on_policy_decision()  │   ─► queue: turn(policy)
                          │  _on_observation()      │   ─► queue: turn(observation)
                          │  _on_finding()          │   ─► queue: finding
                          │  _on_turn_complete()    │   ─► queue: turn(complete)
                          │  _run_safe() finally    │   ─► queue: done / probe_error
                          │                         │
                          │  queue.Queue() ────────►│   drained by SSE route
                          │  threading.Event ──────►│   stop() signal
                          └─────────────────────────┘
```

## Threading model

- `HackerLoop` already runs synchronously in whatever thread you start it on. `ProbeRunner.start()` spawns a single `threading.Thread(daemon=True, target=self._run_safe)` and that thread calls `super().run()` (i.e. `HackerLoop.run()`) inside a try/except that wraps the result, operator-cancel, and unexpected exceptions into the final `done` / `probe_error` event. No subprocess.
- Per-turn hook invocations happen on the loop thread; each one pushes a structured `dict` onto a `queue.Queue`. The queue is thread-safe (stdlib).
- The SSE endpoint runs on the HTTP handler thread; it calls `runner.events()` which `queue.get()`s with a timeout in a loop. When the loop thread emits a `done` or `probe_error` event, `events()` returns, the handler writes the final SSE frame, and the response closes.
- Daemon thread: when the server process shuts down, the loop dies with it. Acceptable for a single-operator dashboard; not acceptable for unattended production.

## Cancellation

- `ProbeRunner` carries `self._stop_event = threading.Event()`. `stop()` sets it.
- The overridden `_on_turn_complete` hook checks `if self._stop_event.is_set(): raise _StopRequested()`. `_StopRequested` is caught in `_run_safe()`, which emits a final `done` event with `stop_reason="operator_cancel"` (plus the matching `turns` / `*_count` fields) and then invokes the `on_finished` callback that clears `_PROBE_SLOT` on the server side.
- Cancellation is *between turns*. An in-flight LLM call or HTTP request will finish (no thread.terminate, no signal-based kill — those aren't safe in Python). Worst-case wait: one LLM round-trip plus one HTTP round-trip ≤ a few seconds at the configured timeouts.

## One-at-a-time guard

- Module-level `_PROBE_SLOT: ProbeRunner | None = None` in `server.py`.
- `POST /api/probe/start` checks the slot under a `threading.Lock`. If non-`None` and the runner reports `is_running()`, returns `409 Conflict`. Otherwise stores the new runner.
- When the loop thread finishes (success, error, or cancel), the runner clears the slot in a `finally`.

## SSE framing

- Response status `200`, `Content-Type: text/event-stream; charset=utf-8`, `Cache-Control: no-cache`, `X-Accel-Buffering: no` (defensive: tells nginx-style intermediaries not to buffer, even though we bind loopback by default).
- The handler writes each event as bytes via `wfile.write` + `wfile.flush` — no `Content-Length`, no claimed chunked encoding. `BaseHTTPRequestHandler` doesn't auto-emit chunk framing, but SSE doesn't need it: each event is `\n\n`-terminated, the client parses incrementally, and the TCP connection naturally closes after the loop emits `done` or `probe_error`. The `Connection: keep-alive` header that an earlier draft listed is intentionally absent — see [06-server-routes.md](06-server-routes.md) §"Notes on the wire format" for the rationale.

## Data flow per turn

The PROBE tab visualises six discrete steps per turn. Each step is its own queue event so the UI updates incrementally rather than in one bulk render at turn-end. See [02-hacker-loop-hooks.md](02-hacker-loop-hooks.md) for the hook list and [07-sse-contract.md](07-sse-contract.md) for the exact event payloads.

```
Step               Hook                      SSE event                       Frontend update
────────────────────────────────────────────────────────────────────────────────────────────
1. model returns   _on_llm_response          turn(stage=action_pending)      action card created, raw text shown
2. action parsed   _on_action_parsed         turn(stage=action_parsed)       raw replaced with parsed action;
                                                                              ⚠ recovered prefix if needed
3. policy decides  _on_policy_decision       turn(stage=policy)              green ✓ / red ✗ badge
4. http response   _on_observation           turn(stage=observation)         observation card (get/post only)
5. finding!        _on_finding (0…N)         finding(…)                      finding badge row
6. turn complete   _on_turn_complete         turn(stage=complete)             turn card sealed (outcome class)
end of loop        finally in _run_safe      done(…) or probe_error(…)       timeline banner
```

Each `turn` event carries `turn` (1-based int) so the frontend updates the existing card in place; subsequent stages mutate the *same* DOM card via `textContent` on inner slots, not by replacing the card. See [07-sse-contract.md](07-sse-contract.md) for the per-stage event payload shapes.
