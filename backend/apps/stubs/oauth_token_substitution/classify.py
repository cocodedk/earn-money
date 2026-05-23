"""Stub 2.16 — passive OAuth evidence classification."""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs

from apps.stubs._shared.types import Confidence

_OAUTH_PATHS = frozenset({"/oauth", "/oidc", "/authorize", "/callback", "/token", "/sso"})
_OAUTH_PARAMS = frozenset({
    "client_id", "redirect_uri", "response_type", "scope",
    "state", "code", "access_token", "id_token", "code_challenge",
})


@dataclass(frozen=True)
class PassiveOAuthEvidence:
    detected: bool
    confidence: Confidence
    artifact_kind: str
    observed_parameters: list[str]
    flow_url: str


def classify_passive_oauth_evidence(response: object) -> PassiveOAuthEvidence:
    """Detect OAuth/OIDC flow evidence from a response."""
    url: str = getattr(response, "url", "") or ""
    body: str = getattr(response, "text", "") or ""

    parsed = urlparse(url)
    params = {k for k in parse_qs(parsed.query)}
    observed = list(params & _OAUTH_PARAMS)

    path_hit = any(p in parsed.path for p in _OAUTH_PATHS)
    param_hit = len(observed) >= 2

    if not path_hit and not param_hit:
        # Check body for OAuth-like links
        if not any(p in body for p in ("client_id=", "redirect_uri=", "response_type=")):
            return PassiveOAuthEvidence(
                detected=False, confidence="low",
                artifact_kind="unknown", observed_parameters=[], flow_url=url,
            )

    artifact = "authorization_code" if "code" in observed else "unknown"
    return PassiveOAuthEvidence(
        detected=True, confidence="low",
        artifact_kind=artifact, observed_parameters=observed, flow_url=url,
    )
