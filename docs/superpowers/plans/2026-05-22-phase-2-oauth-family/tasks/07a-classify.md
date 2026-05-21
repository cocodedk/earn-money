# Task 07a — Stub 2.15: write and verify `classify.py`

Implement the `inspect_authorization_url` helper and its unit tests.

**Files:**
- Create: `backend/apps/stubs/oauth_missing_state/classify.py`
- Create: `backend/apps/stubs/oauth_missing_state/tests/test_classify.py`

**Depends on:** Task 02, Task 06 (fixture running)

**Continues in:** [07b-runner.md](07b-runner.md)

---

- [ ] **Step 1: Write failing test for `inspect_authorization_url`**

`backend/apps/stubs/oauth_missing_state/tests/test_classify.py`:

```python
"""Unit tests for stub 2.15 classification helpers."""
from __future__ import annotations
import pytest
from apps.stubs.oauth_missing_state.classify import (
    inspect_authorization_url,
    OAuthUrlInspection,
)


def test_missing_state_detected_high_confidence():
    url = (
        "https://idp.example/authorize"
        "?client_id=abc&redirect_uri=https%3A%2F%2Fapp.example%2Fcb"
        "&response_type=code&scope=openid"
    )
    result = inspect_authorization_url(url)
    assert result.is_oauth_authorization_request is True
    assert result.has_state is False
    assert result.confidence == "high"
    assert "state" in result.missing_parameters


def test_state_present_not_reported():
    url = (
        "https://idp.example/authorize"
        "?client_id=abc&redirect_uri=https%3A%2F%2Fapp.example%2Fcb"
        "&response_type=code&scope=openid&state=xyz"
    )
    result = inspect_authorization_url(url)
    assert result.has_state is True
    assert result.confidence != "high" or result.is_oauth_authorization_request is False


def test_nonce_and_pkce_do_not_replace_state():
    url = (
        "https://idp.example/authorize"
        "?client_id=abc&redirect_uri=https%3A%2F%2Fapp.example%2Fcb"
        "&response_type=code&scope=openid&nonce=n1&code_challenge=ch&code_challenge_method=S256"
    )
    result = inspect_authorization_url(url)
    assert result.has_state is False
    assert result.has_nonce is True
    assert result.has_pkce is True
    assert "state" in result.missing_parameters


def test_non_oauth_url_not_reported():
    result = inspect_authorization_url("https://example.com/login")
    assert result.is_oauth_authorization_request is False


def test_medium_confidence_partial_params():
    url = "https://idp.example/authorize?client_id=abc&scope=openid"
    result = inspect_authorization_url(url)
    assert result.is_oauth_authorization_request is True
    assert result.confidence == "medium"


def test_malformed_url_returns_not_oauth():
    result = inspect_authorization_url("not a url %%")
    assert result.is_oauth_authorization_request is False
```

- [ ] **Step 2: Run — verify FAIL**

```bash
cd backend && python -m pytest apps/stubs/oauth_missing_state/tests/test_classify.py -v 2>&1 | grep -E "FAILED|ERROR|ImportError"
# Expected: ImportError or FAILED (classify.py does not exist yet)
```

- [ ] **Step 3: Write `classify.py`**

```python
"""Stub 2.15 — OAuth authorization URL inspection helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urlparse, parse_qs

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
    confidence: Literal["low", "medium", "high"]
    missing_parameters: list[str]
    observed_parameters: list[str]
    authorization_url: str
    authorization_path: str


def inspect_authorization_url(url: str) -> OAuthUrlInspection:
    """Inspect a URL for OAuth authorization request patterns.

    Returns an OAuthUrlInspection. `is_oauth_authorization_request` is
    False when the URL is not parseable or lacks sufficient OAuth signals.
    """
    try:
        parsed = urlparse(url)
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    except Exception:
        return _not_oauth(url)

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
    confidence: Literal["low", "medium", "high"] = (
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
```

- [ ] **Step 4: Run — verify PASS**

```bash
cd backend && python -m pytest apps/stubs/oauth_missing_state/tests/test_classify.py -v
# Expected: all green
```
