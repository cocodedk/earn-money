"""Stub 2.22 — tenant-org-join-abuse flaw classification helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from apps.stubs._shared.types import Confidence


class TenantJoinFlawKind(str, Enum):
    UNAUTHORIZED_JOIN = "unauthorized_tenant_join"
    INVITE_REQUIRED = "invite_required_respected"
    SEPARATE_TENANT_CREATED = "separate_tenant_created"


_WORKSPACE_PATH_HINTS = frozenset({
    "workspace", "org", "organization", "tenant", "team", "join",
})
_JOIN_SURFACE_KEYWORDS = frozenset({"join", "workspace", "organization", "tenant", "team"})
_SUCCESS_MARKERS = frozenset({
    "tenant_org_join_abuse_vulnerable",
    "tenant_org_join_abuse_joined_existing_tenant",
    "workspace_member",
})
_REJECT_MARKERS = frozenset({
    "tenant_org_join_abuse_invite_required",
    "tenant_org_join_abuse_pending_approval",
})
_SEPARATE_TENANT_MARKER = "tenant_org_join_abuse_separate_tenant_created"


@dataclass(frozen=True)
class TenantJoinFlawClassification:
    kind: TenantJoinFlawKind
    endpoint_url: str
    http_method: str
    confidence: Confidence
    status: Literal["candidate", "confirmed", "rejected", "stale"]
    observed_fields: list[str] = field(default_factory=list)


def classify_join_surface(
    response: object, endpoint_url: str,
) -> TenantJoinFlawClassification | None:
    """Return low-confidence candidate when response looks like a tenant-join surface."""
    status_code: int = getattr(response, "status_code", 0)
    if status_code not in (200, 201):
        return None
    if not any(h in endpoint_url.lower() for h in _WORKSPACE_PATH_HINTS):
        return None
    body: str = (getattr(response, "text", "") or "").lower()
    if not any(kw in body for kw in _JOIN_SURFACE_KEYWORDS):
        return None
    method: str = getattr(getattr(response, "request", None), "method", "GET") or "GET"
    return TenantJoinFlawClassification(
        kind=TenantJoinFlawKind.UNAUTHORIZED_JOIN,
        endpoint_url=endpoint_url,
        http_method=method,
        confidence="low",
        status="candidate",
    )


def classify_join_success(
    response: object, endpoint_url: str, *, tenant_id: str,
) -> TenantJoinFlawClassification | None:
    """Detect when secondary account successfully joins an existing tenant without invite."""
    status_code: int = getattr(response, "status_code", 0)
    if status_code not in (200, 201):
        return None
    body: str = (getattr(response, "text", "") or "").lower()
    if _SEPARATE_TENANT_MARKER in body:
        return None
    if any(m in body for m in _REJECT_MARKERS):
        return None
    if not any(m in body for m in _SUCCESS_MARKERS):
        return None
    method: str = getattr(getattr(response, "request", None), "method", "POST") or "POST"
    return TenantJoinFlawClassification(
        kind=TenantJoinFlawKind.UNAUTHORIZED_JOIN,
        endpoint_url=endpoint_url,
        http_method=method,
        confidence="high",
        status="confirmed",
    )


def classify_rejected_join(
    response: object, endpoint_url: str,
) -> TenantJoinFlawClassification | None:
    """Detect when the server correctly rejects an unauthorized join attempt."""
    status_code: int = getattr(response, "status_code", 0)
    body: str = (getattr(response, "text", "") or "").lower()

    if status_code in (401, 403):
        method: str = getattr(getattr(response, "request", None), "method", "POST") or "POST"
        return TenantJoinFlawClassification(
            kind=TenantJoinFlawKind.INVITE_REQUIRED,
            endpoint_url=endpoint_url,
            http_method=method,
            confidence="high",
            status="rejected",
        )

    if status_code in (200, 201) and _SEPARATE_TENANT_MARKER in body:
        method = getattr(getattr(response, "request", None), "method", "POST") or "POST"
        return TenantJoinFlawClassification(
            kind=TenantJoinFlawKind.SEPARATE_TENANT_CREATED,
            endpoint_url=endpoint_url,
            http_method=method,
            confidence="high",
            status="rejected",
        )

    return None
