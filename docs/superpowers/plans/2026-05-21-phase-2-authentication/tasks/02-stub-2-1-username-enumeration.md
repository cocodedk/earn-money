# Slice 02 — Stub 2.1 username enumeration (canary)

> Spec: [01-username-enumeration.md](../../../specs/2026-05-18-VULN-SCANNING-COOK-BOOK/02-authentication/01-username-enumeration.md)
> Depends on slice 01 (shared auth infra).
> First Phase 2 stub that registers a runner.

## What it does

For each authorised target (RoE `allow_active_login_probes=True`):

1. Declare a login-behaviour `ProbeBudget` from
   [shared-infra F](../shared-infra/F-active-safety.md).
2. Discover one or more `AuthForm` instances via `discover_forms()` (or
   bounded GET probes against `candidate_login_paths()` when the
   crawler hasn't seeded any).
3. For each form within budget:
   a. Generate one `invalid_identifier` via `generate_invalid_identifier()`.
   b. Optionally read one `valid_identifier` from `roe.authorized_test_accounts`.
   c. Build a `ProbePair` via `build_probe_pair()`.
   d. Re-fetch the form for CSRF if needed (per-request callback).
   e. Refuse unsafe `GET` credential forms before any submit.
   f. Submit the invalid probe and, when `valid_request` exists, the valid
      probe via the `_shared/http.guard()` path.
   g. `normalize()` + `diff()` both responses.
   h. Abort the current form on CAPTCHA / WAF / lockout / rate-limit /
      MFA evidence.
   i. Emit a `UsernameEnumerationFinding` per `differentiators` list.

## Confidence + status mapping

Per spec table:

* `confirmed` / `high`: valid + invalid controls, multiple differentiators.
* `confirmed` / `medium`: valid + invalid controls, single stable differentiator.
* `candidate` / `low`: invalid-only with "user not found" wording.
* `rejected` / `high`: no differentiators after normalization.
* `stale` / `low`: CAPTCHA / lockout / WAF / TLS aborts.
* event-only refusal: RoE disabled, unsafe method, missing fixture validation,
  or budget exhausted. These do not create Findings.

## RoE gating

At the top of `run()`:

```python
if not roe.allow_active_login_probes:
    Event.log(type=EventType.AUTH_PROBE_REFUSED,
              scan_run=..., data={"stub": "2.1", "reason": "roe_disabled"})
    return
```

The scope-enforcement guard still fires first via `@guarded_runner("2.1")`.
This adds Phase-2-specific gating on top. RoE refusal happens before passive
candidate-path discovery so disabled programs make zero network requests.

## Tests

* Discovery yields a login form → ProbePair built → both submits fire.
* Discovery yields no form → `AUTH_FIXTURE_REQUIRED` when fixture validation
  is missing, otherwise no submits, no Finding, no crash.
* RoE disabled → AUTH_PROBE_REFUSED event, no submits.
* Unsafe GET login form → AUTH_PROBE_REFUSED reason=`unsafe_method`, no submits.
* Probe budget exhausted before a repeat → stale/candidate, no confirmed Finding.
* CAPTCHA / lockout / WAF response → abort current form, no confirmed Finding.
* Out-of-scope target → guard() rejects before any form discovery (covered
  by slice G's parametrized OOS test).
* Differentiator detected → Finding row with category=`auth_username_enum`.
* Identical responses → Finding row with `status=rejected, confidence=high`.

## Acceptance

* 100% line + branch coverage on the runner + helpers.
* spec-review report at
  `docs/superpowers/spec-reviews/2026-05-21-stub-2.1-username-enumeration.md`
  matching every spec assertion.
* Live smoke against `juiceshop.cocode.dk`. DVWA / WebGoat are optional only
  after their concrete login endpoints are recorded in the spec-review.
* em-frontend ping: "Stub 2.1 emits Finding.category=`auth_username_enum`;
  AUTH_PROBE_REFUSED + AUTH_FINDING_CANDIDATE events now firing."

## Commit

`feat(stubs): 2.1 username enumeration runner + canary live-smoke`
