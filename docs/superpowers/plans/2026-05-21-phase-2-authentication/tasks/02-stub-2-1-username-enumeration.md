# Slice 02 — Stub 2.1 username enumeration (canary)

> Spec: [`../../../specs/2026-05-18-VULN-SCANNING-COOK-BOOK/02-authentication/01-username-enumeration.md`]
> Depends on slice 01 (shared auth infra).
> First Phase 2 stub that registers a runner.

## What it does

For each authorised target (RoE `allow_active_login_probes=True`):

1. Discover one or more `AuthForm` instances via `discover_forms()` (or
   bounded GET probes against `candidate_login_paths()` when the
   crawler hasn't seeded any).
2. For each form:
   a. Generate one `invalid_identifier` via `generate_invalid_identifier()`.
   b. Optionally read one `valid_identifier` from `roe.authorized_test_accounts`.
   c. Build a `ProbePair` via `build_probe_pair()`.
   d. Re-fetch the form for CSRF if needed (per-request callback).
   e. Submit both probes via the `_shared/http.guard()` path.
   f. `normalize()` + `diff()` both responses.
   g. Emit a `UsernameEnumerationFinding` per `differentiators` list.

## Confidence + status mapping

Per spec table:

* `confirmed` / `high`: valid + invalid controls, multiple differentiators.
* `confirmed` / `medium`: valid + invalid controls, single stable differentiator.
* `candidate` / `low`: invalid-only with "user not found" wording.
* `rejected` / `high`: no differentiators after normalization.
* `stale` / `low`: CAPTCHA / lockout / WAF / TLS / RoE-disabled aborts.

## RoE gating

At the top of `run()`:

```python
if not roe.allow_active_login_probes:
    Event.log(type=EventType.AUTH_PROBE_REFUSED,
              scan_run=..., data={"stub": "2.1", "reason": "roe_disabled"})
    return
```

The scope-enforcement guard still fires first via `@guarded_runner("2.1")`.
This adds Phase-2-specific gating on top.

## Tests

* Discovery yields a login form → ProbePair built → both submits fire.
* Discovery yields no form → no submits, no Finding, no crash.
* RoE disabled → AUTH_PROBE_REFUSED event, no submits.
* Out-of-scope target → guard() rejects before any form discovery (covered
  by slice G's parametrized OOS test).
* Differentiator detected → Finding row with category=`auth_username_enum`.
* Identical responses → Finding row with `status=rejected, confidence=high`.

## Acceptance

* 100% line + branch coverage on the runner + helpers.
* spec-review report at
  `docs/superpowers/spec-reviews/2026-05-21-stub-2.1-username-enumeration.md`
  matching every spec assertion.
* Live smoke against `juiceshop.cocode.dk` (DVWA / WebGoat too, if their
  fixtures support the assertion shape).
* em-frontend ping: "Stub 2.1 emits Finding.category=`auth_username_enum`;
  AUTH_PROBE_REFUSED + AUTH_FINDING_CANDIDATE events now firing."

## Commit

`feat(stubs): 2.1 username enumeration runner + canary live-smoke`
