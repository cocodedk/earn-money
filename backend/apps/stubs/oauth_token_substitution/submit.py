"""Stub 2.16 — two-account OAuth substitution test."""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse, parse_qs

from apps.stubs._shared.types import Confidence


@dataclass
class SubstitutionResult:
    substitution_attempted: bool
    substitution_accepted: bool | None
    identity_mismatch_observed: bool | None
    status: Literal["candidate", "confirmed", "rejected", "stale"]
    confidence: Confidence
    artifact_kind: str
    flow_url: str


def run_substitution_test(
    *,
    base_url: str,
    cred_a: tuple[str, str],
    cred_b: tuple[str, str],
    http: object,
) -> SubstitutionResult:
    """Perform a safe two-account authorization code substitution test.

    - Log in as account A, capture auth code.
    - Log in as account B in a separate session.
    - Substitute account A's code into account B's callback.
    - Check whether the resulting identity is account A (wrong) or rejected.
    """
    user_a, pass_a = cred_a
    user_b, pass_b = cred_b

    # Login A
    resp_a = http.post(f"{base_url}/login", json={"username": user_a, "password": pass_a})
    if resp_a.status_code != 200:
        return SubstitutionResult(
            substitution_attempted=False, substitution_accepted=None,
            identity_mismatch_observed=None, status="candidate",
            confidence="low", artifact_kind="authorization_code", flow_url=base_url,
        )
    token_a = resp_a.json().get("token", "")

    # Authorize as A — capture code from redirect Location
    redirect_uri = f"{base_url}/oauth/callback"
    auth_resp = http.get(
        f"{base_url}/oauth/authorize",
        headers={"X-Session-Token": token_a},
        params={
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": secrets.token_hex(8),
        },
    )
    location = auth_resp.headers.get("Location", "")
    code_a = parse_qs(urlparse(location).query).get("code", [None])[0]
    if not code_a:
        return SubstitutionResult(
            substitution_attempted=False, substitution_accepted=None,
            identity_mismatch_observed=None, status="candidate",
            confidence="low", artifact_kind="authorization_code", flow_url=base_url,
        )

    # Login B — separate session
    resp_b = http.post(f"{base_url}/login", json={"username": user_b, "password": pass_b})
    if resp_b.status_code != 200:
        return SubstitutionResult(
            substitution_attempted=False, substitution_accepted=None,
            identity_mismatch_observed=None, status="candidate",
            confidence="low", artifact_kind="authorization_code", flow_url=base_url,
        )
    token_b = resp_b.json().get("token", "")

    # Substitute A's code into B's callback
    cb_resp = http.post(
        f"{base_url}/oauth/callback",
        json={"code": code_a},
        headers={"X-Session-Token": token_b},
    )
    if cb_resp.status_code != 200:
        return SubstitutionResult(
            substitution_attempted=True, substitution_accepted=False,
            identity_mismatch_observed=False, status="rejected",
            confidence="high", artifact_kind="authorization_code", flow_url=base_url,
        )

    result_marker = cb_resp.json().get("marker", "")
    wrong_identity = result_marker and "user_a" in result_marker and user_b != "user_a"

    return SubstitutionResult(
        substitution_attempted=True,
        substitution_accepted=True,
        identity_mismatch_observed=wrong_identity,
        status="confirmed" if wrong_identity else "candidate",
        confidence="high" if wrong_identity else "medium",
        artifact_kind="authorization_code",
        flow_url=base_url,
    )
