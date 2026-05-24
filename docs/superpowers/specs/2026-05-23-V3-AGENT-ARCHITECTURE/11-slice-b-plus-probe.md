---
slug: slice-b-plus-probe
status: done         # draft | in-progress | done
date: 2026-05-24
implemented: 2026-05-24
---

# Slice B-plus - Narrow Probe + Evidence Contract

Minimal next slice after the Juice Shop scoreboard discovery. This is not the full probe/verify
system. It teaches the agent to investigate one discovered thing and turn it into one evidenced
claim.

## Purpose

Slice 1 proves:

1. The agent can discover a hidden route.
2. The agent can navigate to it.
3. The agent can create a candidate note.

B-plus proves the next step:

1. The agent forms a concrete hypothesis about the discovered page.
2. The agent probes it with read-only target interactions.
3. The agent records evidence that supports or refutes one claim.
4. The agent submits a candidate with repro steps and evidence refs.

Example claim:

> `/#!/score-board` is accessible without authentication and exposes the Score Board view.

## Scope

### In scope

- Add the `probe` phase to the scoreboard mission flow: `recon -> enumerate -> probe -> report`.
- Add executable schemas for:
  - `click`
  - `http_request`
- Implement `click` through the Playwright driver using controller-assigned element IDs.
- Implement `http_request` for same-origin `GET` and `HEAD` only.
- Persist `http_request` results as `AgentObservation(observation_type="http")`.
- Persist `click` results as normal page observations.
- Extend the system prompt with `click` and `http_request` action schemas.
- Extend `submit_candidate` output guidance with a minimal evidence contract.
- Add tests for schema validation, scope enforcement, method restrictions, controller execution,
  prompt inclusion, and phase auto-advance.

### Out of scope

- `fill_form`
- `submit_form`
- `POST`, `PUT`, `PATCH`, `DELETE`, or request bodies
- Custom headers beyond a small controller-owned safe default set
- Authenticated role comparison
- Impact proof or exploit chaining
- Full `verify` phase
- `request_verify`
- Finding promotion from candidate notes
- Report drafting
- Operator checkpoints beyond existing lab-mode gates

## Investigation Loop

When the agent finds the scoreboard page, it should not stop at "route exists." It should run this
loop:

1. **Finding to hypothesis**
   - Store or carry a hypothesis such as:
     `The scoreboard page is reachable unauthenticated and exposes application state.`
2. **Probe**
   - Navigate to the page if needed.
   - Click visible page controls that are already present and safe.
   - Make same-origin `GET` or `HEAD` requests to discovered route/API refs.
3. **Mini verify**
   - Confirm one concrete claim with at least two evidence refs when possible:
     a browser/page observation and an HTTP observation.
   - Mark the claim as `supported`, `refuted`, or `needs_manual_review`.
4. **Output**
   - Submit one candidate with severity, evidence refs, and repro steps.

## Action Contracts

### `click`

```json
{
  "action": "click",
  "goal": "Open the visible scoreboard tab",
  "reason": "The current page observation exposes a safe button/link for the discovered page",
  "hypothesis": "Clicking it will show score board content without auth",
  "element_id": "link_3"
}
```

Rules:

- `element_id` must be a controller-assigned ID from the most recent page observation.
- The controller rejects unknown IDs.
- `click` is allowed in `enumerate` and `probe`; B-plus execution is only required in `probe`.
- After a successful click, the controller returns a fresh `PageObservation`.
- Failed clicks produce an observation with the failure reason and do not throw away the turn.

### `http_request`

```json
{
  "action": "http_request",
  "goal": "Check whether the scoreboard route is directly readable",
  "reason": "Direct GET/HEAD confirms the browser observation with HTTP evidence",
  "hypothesis": "The route returns a successful response without auth",
  "method": "GET",
  "path": "/#!/score-board"
}
```

Rules:

- `method` is `GET` or `HEAD` only.
- `path` must be relative or a controller-known URL ref.
- Same-origin only.
- No request body.
- Response body is truncated and redacted before persistence.
- Persisted HTTP observation includes:
  - `url`
  - `method`
  - `status`
  - `content_type`
  - `redirected`
  - `final_url`
  - `body_excerpt`
  - `body_truncated`
  - `trust: "untrusted_target_content"`

## Candidate Evidence Contract

B-plus keeps `submit_candidate` as the output mechanism, but the `description` and/or note content
must contain this structure:

```json
{
  "claim": "The hidden scoreboard page is accessible without authentication.",
  "verification_status": "supported",
  "severity": "low",
  "evidence_refs": ["action-or-observation-id", "action-or-observation-id"],
  "repro_steps": [
    "Open the target home page in a fresh browser context.",
    "Navigate to /#!/score-board.",
    "Observe the Score Board view loads successfully."
  ],
  "limits": [
    "No authenticated role comparison was performed.",
    "No state-changing requests were sent."
  ]
}
```

Allowed `verification_status` values:

- `supported`
- `refuted`
- `needs_manual_review`

Allowed B-plus severity values:

- `info`
- `low`
- `medium`

The agent should not claim `high` or `critical` in this slice because B-plus does not prove
privilege escalation, sensitive data exposure, or account impact.

## Controller Changes

- Change the scoreboard mission phases to:
  `["recon", "enumerate", "probe", "report"]`.
- Change plateau auto-advance for this mission to include `probe`.
- Keep `verify` out of the automatic flow for now.
- Add parsed dataclasses for `ClickAction` and `HttpRequestAction`.
- Add driver methods:
  - `click(element_id: str)`
  - `http_request(method: str, path: str)`
- Add a lightweight element registry from the last page observation so `click` can map
  controller IDs to Playwright locators safely.
- Consume browser-action and HTTP-request budget counters separately.
- Keep all target content wrapped or marked as untrusted.

## Acceptance Criteria

```gherkin
Given  Juice Shop at the configured lab target
And    the V3 agent discovers /#!/score-board during enumerate
When   the mission enters probe
Then   the agent can click controller-assigned page elements
And    the agent can make same-origin GET/HEAD requests only
And    out-of-scope or mutating HTTP requests are denied before execution
And    HTTP results are persisted as AgentObservation rows with redacted/truncated body excerpts
And    the agent submits a candidate containing claim, verification_status, severity,
       evidence_refs, repro_steps, and limits
And    the mission completes without using fill_form, submit_form, POST, auth comparison,
       request_verify, or Finding promotion
```

## Test Plan

- `backend/apps/agent/tests/test_actions.py`
  - parse valid `click`
  - reject missing `element_id`
  - parse valid `http_request` with `GET` and `HEAD`
  - reject mutating methods
  - reject absolute/out-of-scope URL shapes at schema level where possible
- `backend/apps/agent/tests/test_driver.py`
  - `http_request` allows same-origin `GET`/`HEAD`
  - `http_request` rejects out-of-scope URLs
  - `http_request` truncates large bodies
  - `click` uses registered element IDs
  - unknown element IDs fail safely
- `backend/apps/agent/tests/test_controller.py`
  - probe-phase `http_request` persists an HTTP observation
  - probe-phase `click` persists a page observation
  - mutating `http_request` is denied or schema-invalid before driver execution
- `backend/apps/agent/tests/test_controller_edge.py`
  - plateau auto-advances `enumerate -> probe -> report`
- `backend/apps/agent/tests/test_prompts.py`
  - probe prompt includes `click` and `http_request` schemas
  - report prompt still excludes target-touching actions
- `backend/apps/agent/tests/test_mission_profiles.py`
  - scoreboard profile phases include `probe`
  - probe budgets are present

## Deferred Slice 2

Full slice 2 starts only after B-plus works end to end. It can add:

- form filling and submissions
- RoE-gated mutating requests
- authenticated baseline comparison
- `request_verify`
- deterministic verifier replay
- Finding/Evidence promotion
- report drafting
