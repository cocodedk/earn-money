---
slug: actions
status: done         # draft | in-progress | done
---

# Action Vocabulary

The LLM proposes exactly one typed action per turn. Each action is a JSON object validated
against a strict schema. Freeform reasoning lives in `goal`, `reason`, and `hypothesis`
fields — the controller never infers capabilities from prose.

## Full vocabulary (14 actions)

| Action | Purpose |
|--------|---------|
| `observe_page` | Refresh current DOM/a11y/network/screenshot observation |
| `navigate` | Go to a relative path or discovered URL ref |
| `click` | Click a controller-assigned element ID |
| `fill_form` | Set field values by controller-assigned form/field IDs |
| `submit_form` | Submit a form by controller-assigned form ID |
| `http_request` | Constrained HTTP request, RoE-gated |
| `run_stub` | Invoke an allowlisted v2 stub with target ref |
| `run_tool` | Invoke an allowlisted OSS tool profile (known profiles only) |
| `inspect_asset` | Inspect a discovered same-origin JS/CSS asset; return route/API/string excerpts |
| `store_note` | Record hypothesis, gap, credential label, route, parameter |
| `submit_candidate` | Structured possible finding (LLM does not confirm) |
| `request_verify` | Ask verifier to replay/check evidence |
| `request_phase_transition` | Request phase change with reason + evidence refs |
| `stop` | Done, blocked, or budget exhausted |

## Key constraints

- `click`, `fill_form`, `submit_form` use controller-assigned IDs (`btn_2`, `field_1`,
  `form_1`) — never CSS selectors or XPath.
- `navigate` accepts relative paths or discovered URL refs — never arbitrary hosts. The
  controller validates targets against the mission's scope allowlist: same-origin only by
  default, reject `javascript:`, `data:`, and protocol-relative (`//`) URLs, reject any host
  not in the target's scope. Redirects are followed by Playwright but the controller checks
  the final URL post-navigation and flags out-of-scope landings as a scope edge case
  (checkpoint trigger on real programs).
- `run_stub` and `run_tool` are allowlisted per phase/RoE — the controller offers only
  permitted options. `run_tool` accepts known profiles like
  `{"tool":"nuclei","profile":"safe_http_headers"}`, never arbitrary command strings.
- `inspect_asset` is allowlisted to same-origin discovered JS/CSS assets only. The controller
  fetches, parses, truncates, and returns selected excerpts.
- `submit_candidate` is not confirmation. Promotion to confirmed Finding requires the
  deterministic verifier. The LLM cannot confirm findings.

## Phase-action matrix (strict enforcement)

Target-touching actions are hard-rejected outside their allowed phases. Advisory feedback is
only for non-executing planner guidance ("this belongs in probe; request phase transition").

| Action | Recon | Enumerate | Probe | Verify | Report |
|--------|-------|-----------|-------|--------|--------|
| `observe_page` | yes | yes | yes | yes | no |
| `navigate` | yes | yes | yes | limited (replay) | no |
| `click` | no | yes (safe/nav) | yes | limited (replay) | no |
| `fill_form` | no | yes (no submit) | yes | limited (replay) | no |
| `submit_form` | no | no | yes | limited (replay) | no |
| `http_request` | GET/HEAD | GET/HEAD | RoE-gated | replay only | no |
| `run_stub` | yes | yes | targeted | no (verifier-owned) | no |
| `run_tool` | passive profiles | discovery profiles | RoE-gated | no (verifier-owned) | no |
| `inspect_asset` | yes | yes | targeted | no | no |
| `store_note` | yes | yes | yes | yes | yes |
| `submit_candidate` | no | passive findings only | yes | yes | yes |
| `request_verify` | no | no | yes | yes | no |
| `request_phase_transition` | yes | yes | yes | yes | no |
| `stop` | yes | yes | yes | yes | yes |

"Limited (replay)" in verify means replaying already-identified paths/actions, not exploring
new surface.

"Passive findings only" in enumerate means findings derivable from observation without
state-changing interaction: missing security headers, exposed metadata/version strings,
information disclosure in error pages, debug endpoints in discovered routes. Behavioral
vulnerabilities that require form submission, authentication, or multi-step interaction are
not passive.

## Enforcement pipeline

```
schema validation
→ phase/action allowlist
→ action-specific constraints for that phase
→ RoE/scope/budget policy
→ execution
```
