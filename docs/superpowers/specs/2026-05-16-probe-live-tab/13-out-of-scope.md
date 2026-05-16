# 13 — Out of scope

These were considered and intentionally deferred. Listed here so the next iteration starts informed, not surprised.

## Deferred to v2

### A. Probe queue / multiple concurrent probes

- v1 enforces one-at-a-time with a 409 on conflict. A queue would let the operator launch three probes against three URLs and watch them serialise.
- Lift: introduces priority, fairness, cancellation-while-queued semantics, and a `GET /api/probe/queue` route. None of those are needed for the single-operator use case today.
- When to revisit: when the operator runs more than ~5 probes per day and the 409 friction becomes a real bottleneck.

### B. Persistent probe history

- v1's timeline is ephemeral. Closing the tab loses the events; the SSE stream doesn't replay.
- Right design: a SQLite table `probe_events(run_id, turn, stage, event_json, ts)` written by the probe runner; a `GET /api/probe/runs/<run_id>` route that returns the full event log; an "OPEN PAST RUNS" list above the launcher.
- Lift: ~200 lines of code, one migration, and a small UI list. Wasn't worth doing before we knew what events we actually emit.
- When to revisit: when the operator says "I closed the tab and want to see what happened" more than once.

### C. SSE re-attach / multi-client streaming

- Even without persistence, a re-attach route (`GET /api/probe/stream?since_turn=4`) would let the operator reconnect mid-run and skip the already-rendered turns. v1 just doesn't support it — reconnecting yields only events that arrive after the new connection.
- Worse: v1 uses a single `queue.Queue` consumed by whichever SSE client drains first, so a second client opening against the same `run_id` would *steal* events from the first. v1 forbids this in practice (one tab, one EventSource, browser usage honours this naturally) — see [11-safety-gates.md](11-safety-gates.md) §4a. The clean fix when adding re-attach is per-client cursors over an in-memory event log (essentially a slim version of B without the SQLite).
- Cheap to add if (B) lands — re-attach falls out of "replay from the event log."
- When to revisit: bundled with (B).

### D. `POST /api/probe/stop` route

- The `ProbeRunner.stop()` method exists and works. The form just doesn't expose a CANCEL button in v1.
- Lift: button in the form + 10-line route + 1 test. Trivial.
- When to revisit: the first time the operator launches a 30-turn probe and wants to abort because the model is going in circles.

## Deferred to v3+

### E. Additional TaskTypes

- This spec adds `AGENT_PLANNING`. `EXPLOIT_REASONING` and `EVIDENCE_SUMMARY` were dropped because neither has a routing site in the loop today.
- When the loop gains a "chain validator" turn (after `verified_findings` get a non-zero count), `EXPLOIT_REASONING` becomes the right model selection — add it then.
- When the loop gains a periodic "summarise the last 5 observations to compress prompt size" turn, `EVIDENCE_SUMMARY` becomes the right selection — add it then.
- Adding now creates dead enum surface that confuses implementers without giving any value.

### F. Token-cost visibility (real, not estimated)

- v1 shows `~Nt` per turn via `len(text) // 4`. OpenRouter returns real `usage.{prompt_tokens, completion_tokens}` in the API response.
- Lift: parse `usage` from the provider reply, pass it back through `Provider.complete` (signature change), surface in the SSE turn event.
- When to revisit: when the operator wants to track OpenRouter free-tier credit consumption per probe — when "estimate vs reality" gap matters.

### G. Live RoE editing

- Operator wants to bump `max_requests` mid-run, or unlock `allow_post` without restarting. Today, profile is frozen at runner construction.
- Lift: substantial. RoE is meant to be loaded-once-and-enforced — turning it mutable invites bugs and audit nightmares.
- When to revisit: probably never. The right answer is "stop the run, edit the YAML, start a new run." That's what the CLI does too.

### H. Comparison runs (A/B model probes)

- Run two probes side by side with different `OPENROUTER_MODEL_AGENT_PLANNING` values to see which performs better. Render results in a two-column timeline.
- Lift: a queue + parallel SSE streams + a comparison UI. Significant.
- When to revisit: after enough single-model data lands to make the question "which model is better at this task?" worth answering with engineering time.

### I. Diff-based finding deduplication across runs

- Same probe run twice against the same target → same findings. Today there's no concept of "I've seen this before." A future "RECENT FINDINGS" panel could merge across runs and highlight new vs. familiar.
- Lift: needs (B) persistence and a finding hash function.
- When to revisit: bundled with (B).

### N. URL → program auto-resolution for FROZEN gate

- **Status updated**: v1 now requires an explicit `target_kind` field (`local_lab` / `registered_program`) on the start route. With the operator declaring intent up front, the FROZEN-bypass safety concern this item originally addressed is gone — see [11-safety-gates.md](11-safety-gates.md) §2.
- The remaining value of URL→program auto-resolution is purely UX: the dashboard could pre-fill the `program` field when the operator types a URL that matches a registered program's `scope.md`, saving a click. The safety gate doesn't depend on it.
- Lift: ~40 lines (scope-reader + host-match loop) plus tests.
- When to revisit: when the operator runs probes against multiple registered programs often enough that typing the `program` name becomes annoying.

## Explicitly rejected (won't do)

### J. WebSocket transport

- Already justified in [11-safety-gates.md](11-safety-gates.md) §D. SSE is enough; WebSocket adds protocol weight without enabling anything we need.

### K. `supports_json_schema` registry + per-task fallback chain

- The cursor-agent review proposed this in the JSON-Schema concern. Rejected in [04-robust-action-parsing.md](04-robust-action-parsing.md) §4. Defensive parsing + best-effort `response_format` covers the failure mode without inventing a registry that goes stale weekly.

### L. Server-Sent commands (client → server via SSE)

- SSE is one-way. If we ever need client → server real-time, it'll be a separate `POST` (like `/api/probe/start`) or, if we genuinely need bidirectional streaming, the right tool is HTTP long-poll or WebSocket — at which point we should reconsider the whole architecture, not bolt SSE-misuse onto v1.

### M. Auth (login, sessions, API keys)

- Out of scope by design. Access control = "you have shell on the box" (loopback default) or "host firewall allow-lists your IP" (existing escape hatch). Adding auth means user-management, session storage, password policies — vastly out of scope for an operator dashboard.

## How to use this file when revisiting

Each deferred item has:

- A name (so you can reference it: "we're doing item A from the probe-live-tab spec, §11.A")
- A description of *what* would change
- A lift estimate
- A trigger for when to do it

When you decide to do one, open a new spec under `docs/superpowers/specs/YYYY-MM-DD-probe-<item>/` rather than reviving this one. Each item is its own concern.
