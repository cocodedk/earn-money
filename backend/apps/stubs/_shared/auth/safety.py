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
from typing import Any

from apps.events.models import Event
from apps.events.types import EventType


class RefusalReason(str, Enum):
    """Pre-execution refusal reasons recorded on AUTH_PROBE_REFUSED /
    AUTH_FIXTURE_REQUIRED events. String values are the on-wire
    contract — em-frontend keys off these literals."""
    ROE_DISABLED = "roe_disabled"
    UNSAFE_METHOD = "unsafe_method"
    FIXTURE_REQUIRED = "fixture_required"
    MISSING_SECRET = "missing_fixture_secret"
    BUDGET_EXHAUSTED = "budget_exhausted"


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
    scan_run: Any,
    target: Any,
    stub_id: str,
    reason: RefusalReason,
    details: dict[str, Any] | None = None,
) -> None:
    """Emit the appropriate AUTH_* event for a pre-execution refusal.

    `details` is merged into the event payload alongside the canonical
    fields. Use it to record context like the missing secret's env-var
    name or the budget cap that was hit.
    """
    event_type = (
        EventType.AUTH_FIXTURE_REQUIRED
        if reason in _FIXTURE_EVENT_REASONS
        else EventType.AUTH_PROBE_REFUSED
    )
    payload: dict[str, Any] = {
        "stub": stub_id,
        "target_url": getattr(target, "base_url", None),
        "reason": reason.value,
        "would_have_submitted": False,
    }
    if details:
        payload.update(details)
    Event.log(
        type=event_type, scan_run=scan_run,
        target=target, subject=scan_run, data=payload,
    )
