# Task 09a — Stub 2.16: PassiveOAuthEvidence dataclass + classify.py

**Continues in:** [09b-submit.md](09b-submit.md)

**Files:**
- Create: `backend/apps/stubs/oauth_token_substitution/tests/test_classify.py`
- Create: `backend/apps/stubs/oauth_token_substitution/classify.py`

**Depends on:** Task 04, Task 06

---

- [ ] **Step 1: Write failing tests for `classify.py`**

`backend/apps/stubs/oauth_token_substitution/tests/test_classify.py`:

```python
"""Unit tests for stub 2.16 passive OAuth evidence classification."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest
from apps.stubs.oauth_token_substitution.classify import classify_passive_oauth_evidence


def _resp(status: int, url: str = "", body: str = ""):
    r = MagicMock()
    r.status_code = status
    r.url = url
    r.text = body
    return r


def test_oauth_params_in_redirect_creates_candidate():
    resp = _resp(302, url="https://idp.example/authorize?client_id=abc&redirect_uri=https://app/cb&response_type=code")
    result = classify_passive_oauth_evidence(resp)
    assert result.detected is True
    assert result.confidence == "low"
    assert result.artifact_kind in ("authorization_code", "unknown")


def test_no_oauth_params_not_detected():
    resp = _resp(200, url="https://example.com/login", body="<form></form>")
    result = classify_passive_oauth_evidence(resp)
    assert result.detected is False


def test_oauth_path_in_url_is_detected():
    resp = _resp(302, url="https://example.com/oauth/callback?code=abc123")
    result = classify_passive_oauth_evidence(resp)
    assert result.detected is True


def test_non_oauth_redirect_not_detected():
    resp = _resp(302, url="https://example.com/dashboard")
    result = classify_passive_oauth_evidence(resp)
    assert result.detected is False
```

- [ ] **Step 2: Run — verify FAIL**

```bash
cd backend && python -m pytest apps/stubs/oauth_token_substitution/tests/test_classify.py -v 2>&1 | grep -E "FAILED|ERROR|ImportError"
```

- [ ] **Step 3: Write `classify.py`**

```python
"""Stub 2.16 — passive OAuth evidence classification."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse, parse_qs

_OAUTH_PATHS = frozenset({"/oauth", "/oidc", "/authorize", "/callback", "/token", "/sso"})
_OAUTH_PARAMS = frozenset({
    "client_id", "redirect_uri", "response_type", "scope",
    "state", "code", "access_token", "id_token", "code_challenge",
})


@dataclass(frozen=True)
class PassiveOAuthEvidence:
    detected: bool
    confidence: Literal["low", "medium", "high"]
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
```

- [ ] **Step 4: Run classify tests — verify PASS**

```bash
cd backend && python -m pytest apps/stubs/oauth_token_substitution/tests/test_classify.py -v
```
