"""Active-probe safety helpers — the second gate after RoE.

Every Phase 2 stub builds a `ProbeBudget` declaring its caps, then
threads a `ProbeState` through the discover→build→submit loop. The
state's `can_record_*` methods short-circuit before the next probe
would breach the budget.

Refusals route through `record_refusal()` so the audit trail is
consistent: RoE / unsafe-method / budget-exhausted refusals emit
`AUTH_PROBE_REFUSED`; fixture-required / missing-secret refusals
emit `AUTH_FIXTURE_REQUIRED` (a distinct event the dashboard banners
separately so the operator sees "set up the fixture" vs "RoE blocked").

`assert_can_probe` and `classify_abort` live alongside this module
but depend on `AuthForm` / `NormalizedResponse` which land in the
next subslice. Those helpers register here with stub signatures and
fill in once forms.py + normalize.py exist.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, TYPE_CHECKING

from apps.events.models import Event
from apps.events.types import EventType

if TYPE_CHECKING:
    from apps.scans.models import ScanRun, ScanTargetRun
    from apps.stubs._shared.auth.forms import AuthForm


class RefusalReason(str, Enum):
    """Pre-execution refusal reasons recorded on AUTH_PROBE_REFUSED /
    AUTH_FIXTURE_REQUIRED events. String values are the on-wire
    contract — em-frontend keys off these literals."""
    ROE_DISABLED = "roe_disabled"
    UNSAFE_METHOD = "unsafe_method"
    FIXTURE_REQUIRED = "fixture_required"
    MISSING_SECRET = "missing_fixture_secret"
    BUDGET_EXHAUSTED = "budget_exhausted"
    # Network-layer failure (DNS / TLS / timeout / connection refused).
    # Not a fixture issue — the target is unreachable, not unconfigured.
    # Routes to AUTH_PROBE_REFUSED so the dashboard surfaces it as
    # "probe blocked" rather than "set up the fixture".
    TRANSPORT_ERROR = "transport_error"


class AbortSignal(str, Enum):
    """Post-response abort signals — when the server tells us we hit
    a CAPTCHA / WAF / lockout / rate-limit / MFA boundary, the
    current form's findings cannot be `confirmed`."""
    CAPTCHA = "captcha"
    WAF = "waf"
    LOCKOUT = "lockout"
    RATE_LIMIT = "rate_limit"
    MFA = "mfa"


@dataclass(frozen=True)
class ProbeBudget:
    """Per-stub bounded budget. Caps the number of forms discovered
    and the number of active submits sent."""
    stub_id: str
    max_forms: int
    max_submits: int
    allow_repeat_confirmation: bool


@dataclass
class ProbeState:
    """Mutable counter threaded through a stub's run() to track
    discovery + submit progress against a `ProbeBudget`."""
    forms_seen: int = 0
    submits_made: int = 0

    def record_form(self) -> None:
        self.forms_seen += 1

    def record_submit(self) -> None:
        self.submits_made += 1

    def can_record_form(self, budget: ProbeBudget) -> bool:
        return self.forms_seen < budget.max_forms

    def can_record_submit(self, budget: ProbeBudget) -> bool:
        return self.submits_made < budget.max_submits


# RefusalReason values that map to AUTH_FIXTURE_REQUIRED rather than
# the generic AUTH_PROBE_REFUSED. The dashboard handles them as
# "set up the fixture" UX, distinct from RoE refusals.
_FIXTURE_EVENT_REASONS: frozenset[RefusalReason] = frozenset({
    RefusalReason.FIXTURE_REQUIRED,
    RefusalReason.MISSING_SECRET,
})


def record_refusal(
    *,
    scan_run: "ScanRun",
    target_run: "ScanTargetRun",
    stub_id: str,
    reason: RefusalReason,
    details: dict[str, Any] | None = None,
) -> None:
    """Emit the appropriate AUTH_* event for a pre-execution refusal.

    The event is filed against the specific ``target_run`` so the
    dashboard can link "scan-run → target → refusal" cleanly. Mirrors
    `apps.scans.tasks._process_target_run`'s subject convention.

    `details` is merged into the event payload alongside the canonical
    fields. Use it to record context like the missing secret's env-var
    name or the budget cap that was hit.
    """
    event_type = (
        EventType.AUTH_FIXTURE_REQUIRED
        if reason in _FIXTURE_EVENT_REASONS
        else EventType.AUTH_PROBE_REFUSED
    )
    target = target_run.target
    payload: dict[str, Any] = {
        "stub": stub_id,
        "target_url": target.base_url,
        "reason": reason.value,
        "would_have_submitted": False,
    }
    if details:
        payload.update(details)
    Event.log(
        type=event_type, scan_run=scan_run,
        target=target, subject=target_run, data=payload,
    )


def check_can_probe(
    form: "AuthForm", budget: ProbeBudget, state: ProbeState,
) -> RefusalReason | None:
    """Return a `RefusalReason` if the runner must NOT submit ``form``
    under the current ``state`` + ``budget``, else None.

    The runner calls this before each prospective submit. On a non-
    None return, the runner records the refusal via `record_refusal()`
    and skips the submit.

    Refusal rules:
    * `UNSAFE_METHOD` — form has a `password_field` but `method=GET`.
      Credential-bearing GETs leak the password into URL / Referer /
      proxy logs; the runner refuses unconditionally.
    * `BUDGET_EXHAUSTED` — the next submit would exceed
      ``budget.max_submits``.
    """
    if form.password_field is not None and form.method == "GET":
        return RefusalReason.UNSAFE_METHOD
    if not state.can_record_submit(budget):
        return RefusalReason.BUDGET_EXHAUSTED
    return None
