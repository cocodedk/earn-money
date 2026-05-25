---
slug: submit-candidate-dispatch
status: draft
---

# Submit Candidate Dispatch + Dedup Guard

## Problem

`submit_candidate` has no dedicated branch in `controller_dispatch.py`. It falls through to the
browser-action catch-all, which takes a page screenshot and sends it back to the LLM. The LLM
receives no confirmation that the candidate was recorded, so it resubmits the same finding
repeatedly until plateau kills the mission.

## Solution

Add a dedicated `SubmitCandidateAction` dispatch branch that:

1. Records the candidate (already happens via `record_action` at the top of dispatch).
2. Checks for duplicates — if a candidate with the same category + description already exists
   in this session, send a denial message telling the LLM it's a duplicate.
3. On success, sends a confirmation message back to the LLM: "Candidate accepted: {description}.
   Submit another candidate or stop."
4. Emits an event for the candidate submission.
5. Does NOT take a page screenshot — submit_candidate is a bookkeeping action, not a browser
   action.

## Dedup logic

Two candidates are duplicates when they share the same `category` and a normalized
`description` (lowercase, whitespace-collapsed). The check queries `AgentAction` for prior
`submit_candidate` actions in the same session with matching `args_redacted.category` and
`goal` (which holds the description).

When a duplicate is detected:
- Record the action with `validation_status=DENIED_BUDGET` (reusing existing status — no new
  enum value needed).
- Send a denial message: "Duplicate candidate: you already submitted this finding. Move on to
  a different finding or stop."
- Return False (mission continues).

## Confirmation message format

Use `format_observation_message` with a new observation-style wrapper:

```
<observation trust="controller">
Candidate accepted.
  category: {category}
  description: {description}
You may submit another candidate, transition to verify, or stop.
</observation>
```

The `trust="controller"` distinguishes this from untrusted target content.

## Files to change

- `backend/apps/agent/controller_dispatch.py` — add `SubmitCandidateAction` branch before
  the catch-all, add `_is_duplicate_candidate()` helper
- `backend/apps/agent/tests/test_controller.py` — add tests for candidate dispatch +
  dedup

## Out of scope

- Candidate merging (combining evidence from multiple submissions).
- Candidate scoring or ranking.
- Cross-session dedup (warm-start already handles prior candidates as re-check targets).

## Tests

1. `submit_candidate` records action with category/description in `args_redacted`.
2. `submit_candidate` sends confirmation message back to LLM (not a page observation).
3. Duplicate candidate is denied with denial message.
4. Non-duplicate candidates with different category or description are accepted.
5. `submit_candidate` does not call `_execute_browser_action`.
6. `submit_candidate` emits an event.
