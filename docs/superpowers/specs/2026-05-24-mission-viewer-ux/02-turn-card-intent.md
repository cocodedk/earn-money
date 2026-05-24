# Improvement 1 — TurnCard Intent

## What changes

Below the goal line, always show two new lines (when non-empty):

- **Why:** `action.reason`
- **Expected:** `action.hypothesis`

These are NOT collapsed behind Details.  They are part of the default
card view — the "kid can understand it" layer.

## Data source

`AgentAction.reason` and `AgentAction.hypothesis` — both `string`,
already on the turns endpoint.  Empty strings are skipped.

## Visual

```
✓  #1  recon  22m ago
   Observe the current page to understand the application
   Why: We need to understand what is rendered
   Expected: The page may contain hidden scoreboard references
   Details
```

## Tests

- Render a turn with non-empty reason+hypothesis → both visible
- Render a turn with empty reason → "Why:" line omitted
- Render a turn with empty hypothesis → "Expected:" line omitted
- Render a turn with no actions → neither line shown
