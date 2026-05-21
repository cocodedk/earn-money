# Task 10a — Stub 2.17: AccountLinkingFlawKind enum + classify.py

Implement the classification layer for oauth-account-linking detection.

**Files:**
- Create: `backend/apps/stubs/oauth_account_linking/classify.py`
- Create: `backend/apps/stubs/oauth_account_linking/tests/test_classify.py`

**Depends on:** Task 05, Task 06

**Continues in:** [10b-runner.md](10b-runner.md)

---

- [ ] **Step 1: Write failing tests for `classify.py`**

`backend/apps/stubs/oauth_account_linking/tests/test_classify.py`:

```python
"""Unit tests for stub 2.17 account-linking flaw classification."""
from __future__ import annotations
from unittest.mock import MagicMock
from apps.stubs.oauth_account_linking.classify import (
    classify_link_flaw, AccountLinkingFlawKind,
)


def _resp(status, method="GET", url="", body="", headers=None):
    r = MagicMock()
    r.status_code = status
    r.request = MagicMock()
    r.request.method = method
    r.url = url
    r.text = body
    r.headers = headers or {}
    return r


def test_get_link_action_detected():
    resp = _resp(200, method="GET", url="http://example.com/settings/connections/link/mock",
                 body='{"ok":true,"method_used":"GET"}')
    result = classify_link_flaw(resp, endpoint_url="http://example.com/settings/connections/link/mock")
    assert result is not None
    assert result.kind == AccountLinkingFlawKind.LINK_OVER_GET


def test_missing_state_in_redirect_detected():
    resp = _resp(302, url="http://example.com/auth/link/start",
                 headers={"Location": "http://example.com/oauth/authorize-mock?client_id=x&response_type=code&redirect_uri=http://localhost/cb"})
    result = classify_link_flaw(resp, endpoint_url="http://example.com/auth/link/start")
    assert result is not None
    assert result.kind == AccountLinkingFlawKind.MISSING_STATE


def test_safe_redirect_with_state_not_flagged():
    resp = _resp(302, url="http://example.com/auth/link/start-safe",
                 headers={"Location": "http://example.com/oauth/authorize?client_id=x&state=abc&response_type=code&redirect_uri=http://localhost/cb"})
    result = classify_link_flaw(resp, endpoint_url="http://example.com/auth/link/start-safe")
    assert result is None or result.kind != AccountLinkingFlawKind.MISSING_STATE


def test_callback_without_csrf_detected():
    resp = _resp(200, method="POST", url="http://example.com/auth/link/callback",
                 body='{"ok":true,"csrf_checked":false}')
    result = classify_link_flaw(resp, endpoint_url="http://example.com/auth/link/callback",
                                no_csrf_sent=True)
    assert result is not None
    assert result.kind == AccountLinkingFlawKind.MISSING_CSRF_ON_LINK


def test_client_controlled_provider_identity_detected():
    resp = _resp(200, method="GET", url="http://example.com/auth/link/callback-client-id",
                 body='{"ok":true,"identity_source":"client_parameter"}')
    result = classify_link_flaw(resp, endpoint_url="http://example.com/auth/link/callback-client-id")
    assert result is not None
    assert result.kind == AccountLinkingFlawKind.CALLBACK_ACCEPTS_CLIENT_IDENTITY


def test_non_linking_endpoint_not_flagged():
    resp = _resp(200, url="http://example.com/dashboard", body="<html>Welcome</html>")
    result = classify_link_flaw(resp, endpoint_url="http://example.com/dashboard")
    assert result is None
```

- [ ] **Step 2: Run — verify FAIL**

```bash
cd backend && python -m pytest apps/stubs/oauth_account_linking/tests/test_classify.py -v 2>&1 | grep -E "FAILED|ERROR|ImportError"
```

- [ ] **Step 3: Write `classify.py`**

```python
"""Stub 2.17 — account-linking flaw classification helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal
from urllib.parse import urlparse, parse_qs


class AccountLinkingFlawKind(str, Enum):
    LINK_OVER_GET = "link_over_get"
    MISSING_CSRF_ON_LINK = "missing_csrf_on_link"
    MISSING_STATE = "missing_state"
    STATIC_OR_REUSED_STATE = "static_or_reused_state"
    STATE_NOT_BOUND_TO_SESSION = "state_not_bound_to_session"
    CALLBACK_ACCEPTS_CLIENT_IDENTITY = "callback_accepts_client_identity"
    LINKING_WITHOUT_LOCAL_SESSION = "linking_without_local_session"
    LINKING_WITHOUT_FRESH_AUTH = "linking_without_fresh_auth"
    UNSAFE_CROSS_ACCOUNT_LINK = "unsafe_cross_account_link"


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
```

- [ ] **Step 4: Run classify tests — verify PASS**

```bash
cd backend && python -m pytest apps/stubs/oauth_account_linking/tests/test_classify.py -v
```
