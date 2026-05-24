# Improvement 2 — TurnCard Outcome Digest

## What changes

After intent lines, show a compact "Observed" row for browser actions
that returned a page observation.

Format: `Observed: <title> — <url>` plus small inline counters.

## Data source

`action.observations[0].data` when `observation_type === "page"`:
- `identity.url` — current page URL
- `identity.title` — page title
- `discovered.routes` — array, show count
- `discovered.assets` — array, show count
- `elements` — `{forms, links, inputs, buttons}`, show sum
- `network` — array, show count

## Visual

```
✓  #1  recon  22m ago
   Observe the current page
   Why: Need to understand what is rendered
   Expected: Page may contain hidden scoreboard references
   Observed: OWASP Juice Shop — juiceshop.cocode.dk
             3 routes · 2 assets · 52 requests · 8 elements
   Details
```

## When to skip

- No observations → skip
- `observation_type !== "page"` → skip
- Action types `store_note`, `stop`, `request_phase_transition` → skip
- Non-executed actions → skip

## Tests

- Render turn with page observation → shows URL, title, counters
- Render turn with no observations → "Observed" row hidden
- Render turn with store_note action → "Observed" row hidden
- Render turn with empty discovered → shows "0 routes · 0 assets"
