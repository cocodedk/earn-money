# 07 — SSE event contract

Single source of truth for the event shapes the server emits and the frontend consumes. Both sides cite this file.

## Event types

Four named events. All `data` payloads are valid JSON; the frontend `JSON.parse`s them in handler functions.

### `turn` — incremental turn updates

Fires multiple times per turn (one per stage). The `turn` number identifies the card; `stage` tells the renderer which sub-section of that card to update.

Field presence depends on `stage` — clients merge by `turn`:

```jsonc
// stage = "action_pending"  (fires from _on_llm_response, BEFORE parsing)
{
  "turn": 1,
  "stage": "action_pending",
  "model": "qwen/qwen3-235b-a22b:free",   // string | null
  "raw_excerpt": "{\"tool\":\"get\",…}",  // first 200 chars of LLM reply
  "estimated_tokens": 312                 // (prompt + response) chars // 4
}

// stage = "action_parsed"   (fires from _on_action_parsed, AFTER parsing)
{
  "turn": 1,
  "stage": "action_parsed",
  "action":          { "tool":"get", "category":"http_get", "args":{...} },
  "parse_recovered": false                // true if parse_action_with_recovery had to recover
}

// stage = "policy"          (fires from _on_policy_decision)
{
  "turn": 1,
  "stage": "policy",
  "action":  { ... },                     // echo of the parsed action (same as above)
  "policy":  { "allowed": true, "reason": "GET allowed" }
}

// stage = "observation"     (fires from _on_observation; get/post only)
{
  "turn": 1,
  "stage": "observation",
  "obs": {
    "status": 200,
    "url":    "https://target.example.com/api/users",
    "body_excerpt":  "[{\"id\":1,\"email\":\"…\"}]",
    "content_type":  "application/json"
  }
}

// stage = "complete"        (fires from _on_turn_complete)
{
  "turn": 1,
  "stage": "complete",
  "outcome": "completed" | "denied"
}
```

### Stages (5 distinct, all under event=`turn`)

```
1. action_pending   — LLM returned, raw text + tokens + model id known (pre-parse)
2. action_parsed    — Parsed pydantic action + parse_recovered flag (post-parse)
3. policy           — RoE policy decision rendered (allow/deny + reason)
4. observation      — HTTP response back (skipped for non-HTTP actions)
5. complete         — turn sealed (carries `outcome`)
```

`parse_recovered` lives on the `action_parsed` event (resolves second-reviewer #1) — it cannot live on `action_pending` because parsing hasn't happened yet at that point.

Note: stage 4 (`observation`) fires only for `get`/`post` actions. For `set_header` / `store` / `report_candidate` / `stop`, the turn card goes from `policy` directly to `complete`.

### `finding` — separate event, fires zero-or-more times per turn

```jsonc
{
  "turn": 4,
  "kind": "candidate" | "verified",
  "type": "idor" | "debug_endpoint" | "token_leak" | "unsafe_redirect",
  "path": "/api/users/999",
  "status": 200,
  // type-specific extras:
  "confirmed": true,
  "replay":    "GET /api/users/999 while authenticated as user 1",
  "tokens_masked": ["eyJh***","Bear***"],
  "location":  "https://attacker.example.com/steal"
}
```

The frontend renders this as a badge row attached to the turn card identified by `turn`. The `kind` controls badge colour (candidate=neutral, verified=warn).

### `done` — terminal, fires exactly once per probe

```jsonc
{
  "turns":            7,
  "stop_reason":      "max_turns" | "stop" | "done" | "invalid_action"
                    | "repeated_denials" | "operator_cancel"
                    | "budget_exceeded: …" | "scope_denied: …"
                    | "llm_error",
  "candidates_count": 2,
  "verified_count":   1,
  "denials_count":    0
}
```

After `done`, the server closes the response. The client closes the EventSource and sets `this.closed = true` (resolves review #6).

### `probe_error` — terminal, fires at most once per probe

Renamed from `error` (resolves second-reviewer #6) — `EventSource` already has a built-in transport `error` event with no `data`; using a distinct application-level name (`probe_error`) keeps the client's `addEventListener("probe_error", …)` separate from `es.onerror`.

```jsonc
{
  "message":  "RECON_ENABLED absent at /home/op/repo/RECON_ENABLED. Create the file to enable recon; remove it to halt.",
  "stage":    "gate" | "runtime"
}
```

Same close semantics as `done`. `stage` distinguishes pre-loop failures (gate refused) from mid-loop exceptions (ProbeRunner crashed).

## Internal `_keepalive` event

Not a public event. `ProbeRunner.events()` yields `{"event": "_keepalive", "data": {}}` when the queue is idle (no progress for ≥1 s). The SSE route renders this as a `":\n\n"` comment frame — SSE-spec ignored by `EventSource`, but keeps the TCP connection from going idle through firewalls / load balancers. Operators bind loopback by default so this is defensive, not load-bearing.

## Cross-references

- The renderer side: [09-frontend-probe-client.md](09-frontend-probe-client.md) §"`probe-render.js`"
- The emitter side: [05-probe-runner.md](05-probe-runner.md) § "HackerLoop hook overrides"
- The SSE framing: [06-server-routes.md](06-server-routes.md) § "GET /api/probe/stream"

## Versioning

This contract is **v1**. The frontend doesn't probe a version; both sides land in the same PR. If we later need v2 (e.g., binary diff streams, server-pushed cancel), introduce a new path (`/api/probe/v2/stream`) rather than mutating this one.

## Size discipline

- `raw_excerpt`: 200 chars.
- `body_excerpt`: 200 chars (after the existing `max_response_bytes` budget truncation — so worst case 200 chars of already-truncated body).
- `tokens_masked`: list of strings, each ≤ ~10 chars (mask helper produces `"abcd***"`).
- No `headers` dict in observation events — too much chatter. Only `content_type` is surfaced (it's what the live tab needs to render the badge "JSON / HTML / JS / …").

If a turn would emit > ~2 KB of JSON to the queue, that's a smell — investigate before merging.
