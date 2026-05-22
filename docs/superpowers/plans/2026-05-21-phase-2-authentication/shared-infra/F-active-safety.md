# Slice F — Active-probe safety policy

> Lives in `backend/apps/stubs/_shared/auth/safety.py`.
> Used by every Phase 2 runner before request construction or execution.

## Surface

```python
@dataclass(frozen=True)
class ProbeBudget:
    stub_id: str
    max_forms: int
    max_submits: int
    allow_repeat_confirmation: bool

class RefusalReason(StrEnum):
    ROE_DISABLED = "roe_disabled"
    UNSAFE_METHOD = "unsafe_method"
    FIXTURE_REQUIRED = "fixture_required"
    MISSING_SECRET = "missing_fixture_secret"
    BUDGET_EXHAUSTED = "budget_exhausted"

class AbortSignal(StrEnum):
    CAPTCHA = "captcha"
    WAF = "waf"
    LOCKOUT = "lockout"
    RATE_LIMIT = "rate_limit"
    MFA = "mfa"

def assert_can_probe(form: AuthForm, budget: ProbeBudget, state: ProbeState) -> None
def classify_abort(response: NormalizedResponse) -> AbortSignal | None
def record_refusal(...)
```

## Default budgets

Per-stub task files may tighten these, but they may not raise them without
recording the reason in the per-stub spec-review:

| Surface | max_forms | max_submits | Repeat confirmation |
|---------|-----------|-------------|---------------------|
| Login behaviour | 2 | 4 | yes, if no abort signal |
| Password reset | 1 | 2 | fixture mailbox only |
| MFA | 1 | 2 | no, unless fixture-owned account |
| OAuth / SSO | 1 | 2 | no, unless fixture OAuth client |
| Registration | 1 | 2 | no, unless fixture cleanup exists |

`max_submits` counts active form submissions only. Passive GET discovery still
uses the existing scope guard and token bucket, but it does not consume this
submit budget.

## Refusal rules

The helper refuses before active submission when:

* the relevant RoE knob is false;
* the form would submit credentials or identifiers via `GET`;
* the target has not been fixture-validated for that stub;
* a required fixture secret is absent;
* the next submit would exceed `ProbeBudget.max_submits`.

Every refusal emits `AUTH_PROBE_REFUSED` or `AUTH_FIXTURE_REQUIRED` with
`stub`, `program`, `target_url`, `reason`, and `would_have_submitted=false`.

## Abort rules

After each response normalization, the runner calls `classify_abort()`.
CAPTCHA, WAF, lockout, rate-limit, or MFA evidence stops the current form and
prevents confirmed findings from that form. The stub records `stale` or an
event-only refusal according to its spec table.

## Tests

* Budget exhaustion refuses before the next submit.
* Unsafe `GET` credential forms produce `AUTH_PROBE_REFUSED`.
* Missing fixture secret produces `AUTH_FIXTURE_REQUIRED`.
* CAPTCHA / lockout / WAF / rate-limit / MFA response evidence aborts repeat
  confirmation and prevents `confirmed` classification.
