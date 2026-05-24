---
slug: slice-2-forms-verify
status: draft
---

# Slice 2 — Forms + Verify

Slice 1 proved discovery (observe, navigate, inspect). B-plus proved investigation (click, http_request, probe phase). Slice 2 proves **interaction** — the agent fills forms, submits them, and replays a finding to confirm it.

## Goal

After Slice 2, the agent can:

1. Identify forms on a page (login, registration, search, feedback).
2. Fill individual form fields by element ID.
3. Submit a form by clicking its submit button.
4. Enter the verify phase and replay a candidate finding to confirm or refute it.
5. All form interactions go through Playwright (not raw HTTP) to support SPAs, JS handlers, and client-side validation.

## New actions

### fill_form

Available in: enumerate, probe, verify.

Fills a single input field identified by `element_id` with the given `value`. The element must exist in the current element registry (populated by the most recent page observation).

```json
{
  "action": "fill_form",
  "goal": "...", "reason": "...", "hypothesis": "...",
  "element_id": "input_2",
  "value": "admin@example.com"
}
```

**Validation:**
- `element_id` must be non-empty and present in the driver's element registry.
- `value` must be a string (can be empty to clear a field).
- The driver calls `page.fill(selector, value)` using the registry-resolved selector.

**After fill:** A page observation is returned showing updated page state.

### submit_form

Available in: probe, verify.

Clicks a button or submit element to submit a form. The agent must fill fields first (via one or more `fill_form` turns), then submit.

```json
{
  "action": "submit_form",
  "goal": "...", "reason": "...", "hypothesis": "...",
  "element_id": "btn_0"
}
```

**Validation:**
- `element_id` must be non-empty and present in the element registry.
- The driver calls `page.click(selector)` on the resolved element — same mechanism as `click`, but semantically distinct (counted separately in budget, gated to probe/verify).

**After submit:** A page observation is returned. The observation captures the post-submit page state: new URL, visible text, cookies, network activity. This is the key observation for form-based findings.

## Verify phase

### Purpose

Replay a candidate finding along a narrow, known path to confirm or refute it. No new exploration, no fresh stub/tool sweeps.

### Entry

The LLM requests transition to verify via `request_phase_transition` with `to_phase: "verify"`. The controller approves if at least one `submit_candidate` exists in the session.

### Allowed actions in verify

All probe actions plus: `diff_response`, `compare_baseline`. The agent replays the same browser sequence that produced the candidate: navigate to the page, fill the form with the same values, submit, observe the result, compare with the baseline.

### Exit

The LLM requests transition to report when verification is complete. The controller forces transition to report if the verify budget is exhausted (default: 10 turns in verify).

## Form extraction in observations

The observation builder already parses `InputElement` from the accessibility snapshot. Slice 2 adds **form grouping**: inputs that belong to the same `<form>` element are grouped into a `FormElement` with an `element_id`, action URL, method, and field list.

For SPAs where forms may not use `<form>` tags, the builder falls back to listing inputs individually (current behavior). The agent can still fill and submit them — it just uses `fill_form` on each input and `click` on the submit button.

### Form detection heuristic

1. Parse the accessibility snapshot for `role=form` nodes. Each becomes a `FormElement`.
2. Inputs nested under a form node get the form's `element_id` as their `form_ref`.
3. Buttons nested under a form node with `type=submit` are tagged as form submit buttons.
4. Orphan inputs (no parent form) remain as standalone `InputElement` — the agent can still interact with them.

## Driver additions

Two new methods on `PlaywrightDriver`:

### fill(element_id, value)

```python
async def fill(self, element_id: str, value: str) -> None:
    selector = self._element_registry[element_id]
    await self._page.locator(selector).fill(value)
```

Raises `ValueError` if `element_id` not in registry.

### submit_form(element_id)

Delegates to `click(element_id)` — the submit button click triggers the form submission through Playwright's native event handling.

## Budget

New budget keys:

- `form_fills`: max fill_form actions per mission (default: 50).
- `form_submits`: max submit_form actions per mission (default: 20).
- `verify_turns`: max turns in verify phase (default: 10).

## Dispatch integration

`controller_dispatch.py` gets two new branches:

- `FillFormAction`: calls `driver.fill(element_id, value)`, builds page observation, emits event.
- `SubmitFormAction`: calls `driver.click(element_id)` (same as click), builds page observation, emits event, consumes `form_submits` budget.

Both follow the same pattern as `ClickAction` — execute browser action, record observation, emit event, finish turn.

## Scope and safety

- All form interactions go through Playwright, which inherits the driver's scope validation (same-origin only).
- `fill_form` values are logged in `args_redacted` with sensitive values masked (passwords, tokens).
- No new scope or RoE concerns — form interaction is within the existing browser context.

## Out of scope for Slice 2

- **Mutating HTTP** (POST/PUT via `http_request`): separate slice.
- **run_stub / run_tool**: separate slice.
- **diff_response / compare_baseline implementation**: the action dataclasses and matrix entries exist, but the actual comparison logic (diffing two observations) is deferred. In Slice 2, verify uses the same observe/navigate/fill/submit actions to replay and the agent judges similarity from the observations.
- **File upload**: requires different Playwright API (`set_input_files`), deferred.
- **Multi-select / checkbox / radio**: `fill_form` handles text inputs. Checkbox/radio toggle is a click, not a fill. Deferred to a follow-up if needed.

## Test strategy

1. **Unit tests** for new action dataclasses (`FillFormAction`, `SubmitFormAction`).
2. **Unit tests** for form extraction in observation builder.
3. **Integration tests** for driver `fill` and `submit_form` methods (mock Playwright page).
4. **Controller tests** for dispatch of fill_form and submit_form actions.
5. **Phase transition test**: verify phase entry requires at least one candidate.
6. **Budget tests**: form_fills and form_submits budget enforcement.
7. **End-to-end**: agent fills login form on Juice Shop, submits, observes result.
