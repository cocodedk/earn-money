"""Stub 2.17 — account-linking flaw classification helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal
from urllib.parse import urlparse, parse_qs

from apps.stubs._shared.types import Confidence


class AccountLinkingFlawKind(str, Enum):
    LINK_OVER_GET = "link_over_get"
    MISSING_CSRF_ON_LINK = "missing_csrf_on_link"
    MISSING_STATE = "missing_state"
    CALLBACK_ACCEPTS_CLIENT_IDENTITY = "callback_accepts_client_identity"


_LINK_PATH_HINTS = frozenset({
    "link", "connect", "connections", "social", "sso", "oauth",
    "oidc", "openid", "idp",
})
_OAUTH_PARAMS = frozenset({"client_id", "redirect_uri", "response_type", "scope"})


@dataclass(frozen=True)
class LinkFlawClassification:
    kind: AccountLinkingFlawKind
    endpoint_url: str
    http_method: str
    confidence: Literal["low", "medium", "high"]
    status: Literal["candidate", "confirmed", "rejected", "stale"]
    observed_parameters: list[str] = field(default_factory=list)


def classify_link_flaw(
    response: object,
    *,
    endpoint_url: str,
    no_csrf_sent: bool = False,
) -> LinkFlawClassification | None:
    """Classify a response for account-linking flaws. Returns None if no flaw detected."""
    method: str = getattr(getattr(response, "request", None), "method", "GET") or "GET"
    status_code: int = getattr(response, "status_code", 0)
    body: str = getattr(response, "text", "") or ""
    body_compact = body.lower().replace(" ", "")
    headers: dict = getattr(response, "headers", {})

    parsed_url = urlparse(endpoint_url)
    path_lower = parsed_url.path.lower()

    # Detect link-related endpoint
    is_link_path = any(h in path_lower for h in _LINK_PATH_HINTS)

    # GET link action — state-changing GET
    if method == "GET" and is_link_path and status_code == 200 and (
        '"linked":true' in body_compact or '"method_used":"get"' in body_compact):
        return LinkFlawClassification(
            kind=AccountLinkingFlawKind.LINK_OVER_GET,
            endpoint_url=endpoint_url, http_method=method,
            confidence="medium", status="candidate",
        )

    # 302 redirect — check for missing state in auth URL
    if status_code in (301, 302, 303):
        location = headers.get("Location", "")
        if location:
            loc_parsed = urlparse(location)
            loc_params = {k: v[0] for k, v in parse_qs(loc_parsed.query).items()}
            observed = list(set(loc_params.keys()) & _OAUTH_PARAMS)
            if observed and "state" not in loc_params:
                return LinkFlawClassification(
                    kind=AccountLinkingFlawKind.MISSING_STATE,
                    endpoint_url=endpoint_url, http_method=method,
                    confidence="high", status="candidate",
                    observed_parameters=observed,
                )

    # POST callback without CSRF returned 200
    if method == "POST" and no_csrf_sent and status_code == 200 and (
        '"linked":true' in body_compact or '"csrf_checked":false' in body_compact):
        return LinkFlawClassification(
            kind=AccountLinkingFlawKind.MISSING_CSRF_ON_LINK,
            endpoint_url=endpoint_url, http_method=method,
            confidence="medium", status="candidate",
        )

    # Callback accepts client-controlled provider identity
    if status_code == 200 and "callback-client-id" in path_lower and "client_parameter" in body.lower():
        return LinkFlawClassification(
            kind=AccountLinkingFlawKind.CALLBACK_ACCEPTS_CLIENT_IDENTITY,
            endpoint_url=endpoint_url, http_method=method,
            confidence="high", status="candidate",
        )

    return None
