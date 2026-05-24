"""Stub 2.15 — OAuth authorization URL inspection helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse, parse_qs

from apps.stubs._shared.types import Confidence

_OAUTH_PATHS = frozenset({
    "/authorize", "/oauth/authorize", "/oauth2/authorize",
    "/openid-connect/auth", "/protocol/openid-connect/auth",
    "/connect/authorize",
})
_OAUTH_PARAMS = frozenset({
    "client_id", "redirect_uri", "response_type", "scope",
    "code_challenge", "nonce",
})


@dataclass(frozen=True)
class OAuthUrlInspection:
    is_oauth_authorization_request: bool
    has_state: bool
    has_nonce: bool
    has_pkce: bool
    confidence: Confidence
    missing_parameters: list[str]
    observed_parameters: list[str]
    authorization_url: str
    authorization_path: str


def inspect_authorization_url(url: str) -> OAuthUrlInspection:
    """Inspect a URL for OAuth authorization request patterns."""
    parsed = urlparse(url)
    params = {k: v[0] for k, v in parse_qs(parsed.query).items()}

    observed = [p for p in _OAUTH_PARAMS if p in params]
    is_known_path = any(parsed.path.endswith(p) for p in _OAUTH_PATHS)
    is_oauth = (
        is_known_path
        or ("client_id" in params and ("redirect_uri" in params or "response_type" in params))
    )
    if not is_oauth and len(observed) < 2:
        return _not_oauth(url)

    has_state = "state" in params
    has_nonce = "nonce" in params
    has_pkce = "code_challenge" in params
    missing = ["state"] if not has_state else []

    has_full = {"client_id", "redirect_uri", "response_type"}.issubset(params)
    confidence: Confidence = (
        "high" if has_full and not has_state
        else "medium" if len(observed) >= 2
        else "low"
    )

    return OAuthUrlInspection(
        is_oauth_authorization_request=True,
        has_state=has_state,
        has_nonce=has_nonce,
        has_pkce=has_pkce,
        confidence=confidence,
        missing_parameters=missing,
        observed_parameters=observed,
        authorization_url=url,
        authorization_path=parsed.path,
    )


def _not_oauth(url: str) -> OAuthUrlInspection:
    return OAuthUrlInspection(
        is_oauth_authorization_request=False,
        has_state=False, has_nonce=False, has_pkce=False,
        confidence="low", missing_parameters=[], observed_parameters=[],
        authorization_url=url, authorization_path="",
    )
