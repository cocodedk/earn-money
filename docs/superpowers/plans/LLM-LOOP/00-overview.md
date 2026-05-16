# LLM Probe Loop Implementation Plan (Corrected Order)

## Goal

Build a controlled LLM-driven probe loop for authorized vulnerability testing.

The loop should let the LLM reason about the target, propose the next action, call approved tools, observe results, update memory, and continue until it finds evidence or exhausts its limits.

The system must support different Rules of Engagement, because legal boundaries can come from:

- a client contract
- a HackerOne program
- another bug bounty platform
- a private VDP
- an internal lab
- a local CTF target
- a written test authorization

The LLM must not define the boundary. The RoE profile defines the boundary.

---

## Core principle

The LLM proposes.

The policy engine decides.

The tool layer executes only what policy allows.

```text
LLM suggestion
    ↓
Action schema validation
    ↓
RoE policy check
    ↓
Scope policy check
    ↓
Budget/rate-limit check
    ↓
Tool execution
    ↓
Observation wrapped as untrusted target content
    ↓
Finding verifier
    ↓
Session memory update
```

---

## Non-goals

These are not banned forever. They are not enabled by default.

The scanner should not:

* run brute force unless the RoE explicitly allows it
* run high-volume automation unless the RoE explicitly allows it
* continue into exploit chains unless the RoE allows impact proof
* perform destructive actions unless explicitly allowed
* access out-of-scope hosts
* let the LLM select arbitrary tools
* let the LLM change the base target
* let target content change the agent's instructions
* report weak signals as confirmed vulnerabilities

---

## RoE model

Create a first-class RoE profile.

The RoE profile controls what the agent may do.

Example:

```yaml
name: hackerone-default-safe
scope:
  allowed_hosts:
    - target.example.com
  denied_hosts:
    - "*.internal"
    - "localhost"
    - "127.0.0.1"
    - "169.254.169.254"

traffic:
  max_requests: 100
  max_posts: 20
  max_turns: 25
  max_runtime_seconds: 180
  max_response_bytes: 12000
  delay_between_requests_ms: 500

methods:
  allow_get: true
  allow_post: true
  allow_put: false
  allow_patch: false
  allow_delete: false

testing:
  allow_authenticated_testing: true
  allow_rate_limit_testing: false
  allow_bruteforce: false
  allow_password_spraying: false
  allow_credential_stuffing: false
  allow_exploit_chains: false
  allow_destructive_actions: false
  allow_file_upload_tests: false
  allow_graphql_introspection: true
  allow_openapi_probing: true
  allow_idor_checks: true
  allow_xss_probe_payloads: false
  allow_sqli_probe_payloads: false

evidence:
  require_replay_steps: true
  require_non_destructive_poc: true
  allow_sensitive_data_capture: false
  max_evidence_body_bytes: 1000
```

---

## Main components

| Component            | Role                                                                       |
| -------------------- | -------------------------------------------------------------------------- |
| `RoeProfile`         | Stores legal and program-specific test permissions                         |
| `RoePolicy`          | Decides whether an action is allowed under the current RoE                 |
| `ScopePolicy`        | Enforces hosts, schemes, redirects, IP restrictions, and path safety       |
| `RequestBudget`      | Tracks request count, POST count, turns, runtime, and response size        |
| `ActionSchema`       | Validates LLM actions as typed JSON                                        |
| `ObservationWrapper` | Marks all target responses as untrusted content                            |
| `HttpTool`           | Executes only policy-approved HTTP actions, returns wrapped observations   |
| `HackerSession`      | Stores memory, observations, hypotheses, candidates, and verified findings |
| `FindingVerifier`    | Turns observations into candidate or verified findings                     |
| `HackerLoop`         | Runs think → validate → act → observe → verify                             |
| `CLI`                | Runs the loop from terminal with RoE profile and target config             |

---

## File map

```text
src/earn_money/agent/roe_profile.py
src/earn_money/agent/roe_policy.py
src/earn_money/agent/scope_policy.py
src/earn_money/agent/budget.py
src/earn_money/agent/actions.py
src/earn_money/agent/observations.py          # ← moved up (was Task 8)
src/earn_money/agent/http_tool.py             # ← now depends on observations
src/earn_money/agent/session.py
src/earn_money/agent/finding_verifier.py
src/earn_money/agent/hacker_loop.py
src/earn_money/agent/hacker_loop_cli.py
src/earn_money/engine/active_tick_cli.py
bin/probe-target
```

Test files:

```text
tests/agent/test_roe_profile.py
tests/agent/test_roe_policy.py
tests/agent/test_scope_policy.py
tests/agent/test_budget.py
tests/agent/test_actions.py
tests/agent/test_observations.py
tests/agent/test_http_tool.py
tests/agent/test_session.py
tests/agent/test_finding_verifier.py
tests/agent/test_hacker_loop.py
tests/agent/test_hacker_loop_cli.py
tests/engine/test_active_tick_cli.py
```
