# Non-Goals

Things this change explicitly does NOT do. Each is excluded for a reason; the reason is the test for "should we reconsider?".

## Cross-page persistence

Refreshing the browser tab clears the transcript. The detail panel renders from in-memory `state.turns` populated by the live SSE stream; there is no `localStorage` snapshot, no server-side prompt cache, no API to fetch a past run's prompts.

**Reason:** Adds server-side storage (per-run, per-turn prompt blob = ~5 KB × turns × runs). The dashboard already has SQLite per program; introducing a "live run history" table is a feature, not a debugging aid. Operators who need persistence today can copy-paste from the panel into a note.

**Reconsider when:** Operators report losing context after a browser crash mid-debug.

## Cross-run transcript history

The panel shows only the current run. The next `POST /api/probe/start` clears `state.turns`. There is no "browse past runs" UI.

**Reason:** Same as above — requires server-side storage. Also, comparing prompts across runs is a longer-term observability play; not what this change is for.

## Server-side prompt diffing

The Delta tab computes "what's new this turn" entirely in the browser. The server sends full prompts; the client splits on `=== ` headers and shows only differing sections.

**Reason:** Keeps the server stateless. Splitting is ~30 lines of JS; doing it server-side would add a per-turn diff payload to the SSE event for no UX gain.

## Token / cost accounting

The existing `estimated_tokens` field (a crude `len(text) // 4`) is unchanged. We do NOT add prompt-token counts, completion-token counts, OpenRouter cost lookups, or a per-run cost meter.

**Reason:** Out of scope. The retry-attempt visibility this change delivers is enough to inform a future "model X is wasting calls" decision; cost dashboards are a separate feature.

## Mobile-first layout

The grid collapses to a single column on narrow viewports as a graceful-fail safety, not as a designed mobile experience. We do not test on phones, do not optimise touch targets, and do not commit to mobile usability.

**Reason:** Dashboard runs on operator laptop or VPS-served-to-laptop. Mobile is not a use case.

## Sanitization beyond `textContent`

We rely entirely on `node.textContent = value` to neutralise LLM-controlled strings in the DOM. We do NOT add HTML escaping libraries, content-security-policy headers, or sanitization wrappers.

**Reason:** `textContent` is the correct primitive. Adding a sanitizer would be defence-in-depth against an `innerHTML` bug we don't have; the existing code follows the same rule. A code-review check + the `grep` in `05-test-plan.md` is the discipline.

## Prompt editing / replay

The panel is read-only. We do NOT add "edit this prompt and send it to the model" or "replay this turn with a different model".

**Reason:** That's a fundamentally different feature (LLM playground vs probe observability) and would require new server endpoints, new safety review (replay against the same target counts as a new request that needs RoE checks), and a much bigger spec.

## Animation / transitions

No fade-ins, no slide animations, no skeleton loaders. The panel updates instantly on event arrival.

**Reason:** SSE events arrive at human-readable cadence (one per LLM round-trip). Animations would obscure rather than aid comprehension. Consistent with the rest of the dashboard's no-animation style.
