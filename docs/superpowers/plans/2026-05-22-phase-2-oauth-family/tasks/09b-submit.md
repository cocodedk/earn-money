# Task 09b — Stub 2.16: two-account substitution flow (submit.py)

**Continues from:** [09a-classify.md](09a-classify.md)
**Continues in:** [09c-runner.md](09c-runner.md)

**Files:**
- Create: `backend/apps/stubs/oauth_token_substitution/tests/test_submit.py`
- Create: `backend/apps/stubs/oauth_token_substitution/submit.py`

---

- [ ] **Step 5: Write failing tests for `submit.py`**

`backend/apps/stubs/oauth_token_substitution/tests/test_submit.py`:

```python
"""Tests for stub 2.16 two-account substitution submit."""
from __future__ import annotations
from unittest.mock import MagicMock, call
import pytest
from apps.stubs.oauth_token_substitution.submit import (
    run_substitution_test, SubstitutionResult,
)


def _make_http(login_marker="user_a_marker", callback_marker="user_a_marker",
               login_ok=True, callback_ok=True):
    http = MagicMock()
    def post(url, **kwargs):
        r = MagicMock()
        if "/login" in url:
            r.status_code = 200 if login_ok else 401
            r.json.return_value = {"token": "tok-a", "userId": "user_a"}
        elif "/oauth/callback" in url:
            r.status_code = 200 if callback_ok else 400
            r.json.return_value = {"marker": callback_marker, "userId": "user_a"}
        return r
    def get(url, **kwargs):
        r = MagicMock()
        r.status_code = 200
        if "/oauth/authorize" in url:
            r.status_code = 302
            r.headers = {"Location": "http://localhost/cb?code=code-abc"}
        elif "/me" in url:
            r.json.return_value = {"userId": "user_a", "marker": login_marker}
        return r
    http.post = post
    http.get = get
    return http


def test_confirmed_when_wrong_identity_returned():
    result = run_substitution_test(
        base_url="http://localhost:3000",
        cred_a=("user_a", "pass-a"),
        cred_b=("user_b", "pass-b"),
        http=_make_http(callback_marker="user_a_marker"),
    )
    assert result.substitution_attempted is True
    assert result.identity_mismatch_observed is True
    assert result.status == "confirmed"
    assert result.confidence == "high"


def test_rejected_when_callback_returns_400():
    result = run_substitution_test(
        base_url="http://localhost:3000",
        cred_a=("user_a", "pass-a"),
        cred_b=("user_b", "pass-b"),
        http=_make_http(callback_ok=False),
    )
    assert result.status == "rejected"


def test_login_failure_returns_candidate():
    result = run_substitution_test(
        base_url="http://localhost:3000",
        cred_a=("user_a", "pass-a"),
        cred_b=("user_b", "pass-b"),
        http=_make_http(login_ok=False),
    )
    assert result.status == "candidate"
    assert result.substitution_attempted is False
```

- [ ] **Step 6: Write `submit.py`**

```python
"""Stub 2.16 — two-account OAuth substitution test."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse, parse_qs
import secrets


@dataclass
class SubstitutionResult:
    substitution_attempted: bool
    substitution_accepted: bool | None
    identity_mismatch_observed: bool | None
    status: Literal["candidate", "confirmed", "rejected", "stale"]
    confidence: Literal["low", "medium", "high"]
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
        allow_redirects=False,
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
```

- [ ] **Step 7: Run submit tests — verify PASS**

```bash
cd backend && python -m pytest apps/stubs/oauth_token_substitution/tests/test_submit.py -v
```
