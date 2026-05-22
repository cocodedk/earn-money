"""Stub 2.21 — invitation-abuse flaw classification helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from apps.stubs._shared.body_match import contains_any_lowered
from apps.stubs._shared.types import Confidence


class InviteFlawKind(str, Enum):
    SENSITIVE_PREVIEW = "sensitive_invite_preview"
    RECIPIENT_NOT_BOUND = "recipient_not_bound"
    INVITE_REUSABLE = "invite_reusable"
    ROLE_ESCALATION = "role_escalation"


_INVITE_PATH_HINTS = frozenset({
    "invite", "invitation", "invitations", "join", "accept",
    "team", "workspace", "organization", "tenant", "members",
})
_INVITE_BODY_KEYWORDS = frozenset({
    "invite", "invitation", "join", "workspace", "tenant",
})
_PREVIEW_FIELDS = frozenset({
    "workspace", "tenant", "organization", "role", "invited_by",
    "inviter", "team", "permissions",
})
_ACCEPT_SIGNALS = frozenset({"accepted", "joined", "member_created", "workspace_member"})
_ROLE_RANK: dict[str, int] = {
    "guest": 0, "viewer": 1, "member": 2, "editor": 3, "admin": 4, "owner": 5,
}


@dataclass(frozen=True)
class InviteFlawClassification:
    kind: InviteFlawKind
    endpoint_url: str
    http_method: str
    confidence: Confidence
    status: Literal["candidate", "confirmed", "rejected", "stale"]
    observed_fields: list[str] = field(default_factory=list)
    requested_role: str | None = None
    observed_role: str | None = None


def classify_invite_surface(
    response: object, endpoint_url: str,
) -> InviteFlawClassification | None:
    """Return low-confidence candidate when response looks like an invite surface."""
    status_code: int = getattr(response, "status_code", 0)
    if status_code not in (200, 201):
        return None
    if not any(h in endpoint_url.lower() for h in _INVITE_PATH_HINTS):
        return None
    body: str = (getattr(response, "text", "") or "").lower()
    if not contains_any_lowered(body, _INVITE_BODY_KEYWORDS):
        return None
    method: str = getattr(getattr(response, "request", None), "method", "GET") or "GET"
    return InviteFlawClassification(
        kind=InviteFlawKind.SENSITIVE_PREVIEW,
        endpoint_url=endpoint_url,
        http_method=method,
        confidence="low",
        status="candidate",
    )


def classify_preview_exposure(
    response: object, endpoint_url: str, *, authenticated: bool = False,
) -> InviteFlawClassification | None:
    """Detect unauthenticated GET that leaks workspace/role/inviter details."""
    if authenticated:
        return None
    status_code: int = getattr(response, "status_code", 0)
    if status_code != 200:
        return None
    method: str = getattr(getattr(response, "request", None), "method", "GET") or "GET"
    if method not in ("GET", "HEAD"):
        return None
    body: str = (getattr(response, "text", "") or "").lower()
    exposed = [f for f in _PREVIEW_FIELDS if f in body]
    if not exposed:
        return None
    return InviteFlawClassification(
        kind=InviteFlawKind.SENSITIVE_PREVIEW,
        endpoint_url=endpoint_url,
        http_method=method,
        confidence="medium",
        status="candidate",
        observed_fields=exposed,
    )


def _classify_accept_signal(
    response: object, endpoint_url: str, *, kind: InviteFlawKind,
) -> InviteFlawClassification | None:
    """Return a confirmed high-confidence finding when the response signals invite acceptance."""
    status_code: int = getattr(response, "status_code", 0)
    if status_code not in (200, 201):
        return None
    body: str = (getattr(response, "text", "") or "").lower()
    if not contains_any_lowered(body, _ACCEPT_SIGNALS):
        return None
    method: str = getattr(getattr(response, "request", None), "method", "POST") or "POST"
    return InviteFlawClassification(
        kind=kind,
        endpoint_url=endpoint_url,
        http_method=method,
        confidence="high",
        status="confirmed",
    )


def classify_wrong_recipient(
    response: object, endpoint_url: str,
) -> InviteFlawClassification | None:
    """Detect when an unrelated authenticated session successfully accepts an invite."""
    return _classify_accept_signal(response, endpoint_url, kind=InviteFlawKind.RECIPIENT_NOT_BOUND)


def classify_reuse(
    response: object, endpoint_url: str,
) -> InviteFlawClassification | None:
    """Detect when a previously-used invite token is accepted again."""
    return _classify_accept_signal(response, endpoint_url, kind=InviteFlawKind.INVITE_REUSABLE)


def classify_role_escalation(
    response: object,
    endpoint_url: str,
    *,
    requested_role: str,
    observed_role: str | None,
) -> InviteFlawClassification | None:
    """Detect when accepted role is stronger than the requested role."""
    if observed_role is None:
        return None
    status_code: int = getattr(response, "status_code", 0)
    if status_code not in (200, 201):
        return None
    req_rank = _ROLE_RANK.get(requested_role.lower(), -1)
    obs_rank = _ROLE_RANK.get(observed_role.lower(), -1)
    if obs_rank <= req_rank:
        return None
    method: str = getattr(getattr(response, "request", None), "method", "POST") or "POST"
    return InviteFlawClassification(
        kind=InviteFlawKind.ROLE_ESCALATION,
        endpoint_url=endpoint_url,
        http_method=method,
        confidence="high",
        status="confirmed",
        requested_role=requested_role,
        observed_role=observed_role,
    )
