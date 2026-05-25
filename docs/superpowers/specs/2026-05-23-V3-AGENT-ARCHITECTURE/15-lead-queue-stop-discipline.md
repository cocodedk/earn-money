---
slug: lead-queue-stop-discipline
status: draft
---

# Lead Queue + Stop Discipline

## Problem

The agent finds one thing, submits it, and stops. It doesn't use discoveries as springboards
to investigate further. A hidden admin panel, an API listing, or a form with weak validation
are all leads that should chain into deeper investigation — but the agent treats each finding
as terminal.

## Solution

Add lead tracking and stop discipline to the system prompt. The agent stores leads as notes,
prioritizes them, and must check for uninvestigated leads before stopping.

## Design

### 1. Lead tracking in the Investigation Strategy

Extend the existing `## Investigation Strategy` section in the system prompt with lead
tracking guidance:

```
- When you discover data that references other parts of the application — endpoint paths,
  parameter names, admin panels, vulnerability categories, user roles — store each as a
  store_note(hypothesis) or store_note(route) lead.
- Prioritize leads: route-like references and vulnerability-class hints are high value.
  Generic labels or marketing text are noise — do not store those.
- Prefer API and asset investigation over page DOM when the page structure is opaque.
  If you see a page that likely has a backing API (lists, tables, dashboards), use
  http_request to fetch the data endpoint or inspect_asset to read the JavaScript.
```

### 2. Stop discipline

Add a `## Stop Discipline` section to the system prompt:

```
- Before emitting a stop action, review your stored hypothesis, route, parameter, and
  gap notes. If any high-confidence lead is uninvestigated, choose one and continue.
- If a lead is blocked (requires auth you don't have, needs a tool not available in this
  phase, or is out of scope), store a gap note explaining why and move on.
- Stop only when: all promising leads are investigated or blocked, budget is low (< 3
  turns remaining), or the objective is fully achieved.
```

### 3. API-first investigation guidance

Add to the Investigation Strategy:

```
- When a page contains structured data you cannot fully read (tables, long lists), look
  for the backing API. Common patterns: /api/{resource}, /rest/{resource}, /{resource}.json.
  Use http_request(GET, path) to fetch the raw data.
- JavaScript bundles (inspect_asset on .js files) often reveal API endpoints, route
  definitions, and hidden features. Inspect them early.
```

## Files to change

| File | Action |
|------|--------|
| `backend/apps/agent/llm/prompts.py` | Modify — extend Investigation Strategy + add Stop Discipline |
| `backend/apps/agent/tests/test_prompts.py` | Modify — test new sections present |

## Out of scope

- Code changes to the controller or dispatch (prompt-only change).
- Automated lead extraction from observations (the LLM decides what to note).
- Lead deduplication or scoring (the LLM prioritizes via prompt guidance).
- Target-specific hints (no mention of Juice Shop, DVWA, or any app).

## Tests

1. System prompt contains "Stop Discipline" section.
2. System prompt contains lead tracking guidance (store_note + hypothesis).
3. System prompt contains API-first investigation guidance.
4. All existing prompt tests still pass.
