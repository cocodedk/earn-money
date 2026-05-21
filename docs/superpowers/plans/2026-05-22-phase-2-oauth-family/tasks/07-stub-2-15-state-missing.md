# Task 07 — Stub 2.15: oauth-missing-state detection chain

Implement the detection logic in `oauth_missing_state/`. The skeleton
runner and gate tests already exist.

**Files:**
- Create: `backend/apps/stubs/oauth_missing_state/classify.py`
- Modify: `backend/apps/stubs/oauth_missing_state/runner.py`
- Create: `backend/apps/stubs/oauth_missing_state/tests/test_classify.py`
- Create: `backend/apps/stubs/oauth_missing_state/tests/test_runner.py`

**Depends on:** Task 02, Task 06 (fixture running)

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

- [ ] **Step 5: Write failing integration test**

`backend/apps/stubs/oauth_missing_state/tests/test_runner.py`:

```python
"""End-to-end detection tests for stub 2.15 (oauth-missing-state)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.findings.models import Finding
from apps.programs.loader import Program, get_registry
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._test_factories import seed_target_run
from apps.stubs.oauth_missing_state.runner import run


_MODULE = "apps.stubs.oauth_missing_state.runner"


def _program(knob_on: bool = True) -> Program:
    return Program(
        platform="local", slug="oauth-state-missing",
        scope=Scope(
            platform="local", slug="oauth-state-missing",
            policy="rate-limited-OK",
            in_scope=["oauth-state-missing"], out_of_scope=[],
        ),
        roe=RoE(
            max_requests_per_second=30,
            allow_oauth_probes=knob_on,
            authorized_test_accounts=[],
        ),
    )


def _make_redirect_response(location: str) -> MagicMock:
    r = MagicMock()
    r.status_code = 302
    r.headers = {"Location": location}
    r.text = ""
    return r


@pytest.mark.django_db
def test_missing_state_creates_finding(monkeypatch):
    monkeypatch.setenv("FIXTURE_OAUTH_CLIENT_SECRET", "fixture-value")
    scan_run, target_run = seed_target_run(host="oauth-state-missing", stub_slug="2.15")
    vuln_location = (
        "http://oauth-state-missing:3000/oauth/authorize"
        "?client_id=test-client&redirect_uri=http%3A%2F%2Flocalhost%2Fcb&response_type=code&scope=openid"
    )
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.fetch_for_discovery",
                   return_value=_make_redirect_response(vuln_location)):
            run(scan_run, target_run)

    assert Finding.objects.filter(scan_run=scan_run, stub_slug="2.15").exists()
    finding = Finding.objects.get(scan_run=scan_run, stub_slug="2.15")
    assert finding.confidence == "high"


@pytest.mark.django_db
def test_state_present_no_finding(monkeypatch):
    monkeypatch.setenv("FIXTURE_OAUTH_CLIENT_SECRET", "fixture-value")
    scan_run, target_run = seed_target_run(host="oauth-state-missing", stub_slug="2.15")
    safe_location = (
        "http://oauth-state-missing:3000/oauth/authorize"
        "?client_id=test-client&redirect_uri=http%3A%2F%2Flocalhost%2Fcb"
        "&response_type=code&scope=openid&state=abc123"
    )
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.fetch_for_discovery",
                   return_value=_make_redirect_response(safe_location)):
            run(scan_run, target_run)

    assert not Finding.objects.filter(scan_run=scan_run, stub_slug="2.15").exists()


@pytest.mark.django_db
def test_non_oauth_redirect_no_finding(monkeypatch):
    monkeypatch.setenv("FIXTURE_OAUTH_CLIENT_SECRET", "fixture-value")
    scan_run, target_run = seed_target_run(host="oauth-state-missing", stub_slug="2.15")
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.fetch_for_discovery",
                   return_value=_make_redirect_response("http://oauth-state-missing:3000/login")):
            run(scan_run, target_run)

    assert not Finding.objects.filter(scan_run=scan_run, stub_slug="2.15").exists()


@pytest.mark.django_db
def test_transport_error_emits_refusal(monkeypatch):
    monkeypatch.setenv("FIXTURE_OAUTH_CLIENT_SECRET", "fixture-value")
    scan_run, target_run = seed_target_run(host="oauth-state-missing", stub_slug="2.15")
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.fetch_for_discovery", return_value=None):
            run(scan_run, target_run)

    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    ).exists()
```

- [ ] **Step 6: Add detection chain to `runner.py`**

Replace the `# Detection chain ships...` comment with:

```python
    fixture_url = os.environ.get("FIXTURE_OAUTH_STATE_MISSING_URL", target.base_url)
    acquire_for(program)
    resp = fetch_for_discovery(
        url=fixture_url + "/login",
        target=target,
        program=program,
        follow_redirects=True,
        max_hops=program.roe.max_requests_per_second,
    )
    if resp is None:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id="2.15",
            reason=RefusalReason.TRANSPORT_ERROR,
            details={"detail": "target_unreachable"},
        )
        return

    location = resp.headers.get("Location", "")
    if not location:
        return  # No redirect — no OAuth evidence

    from .classify import inspect_authorization_url
    inspection = inspect_authorization_url(location)
    if not inspection.is_oauth_authorization_request or inspection.has_state:
        return

    _emit_finding(
        scan_run=scan_run, target=target,
        authorization_url=location,
        confidence=inspection.confidence,
    )
```

Add `_emit_finding` and necessary imports at top of `runner.py`:

```python
import os
from apps.findings.models import Finding, FindingStatus, Severity
from apps.stubs._shared.auth.discovery import fetch_for_discovery
from apps.stubs._shared.auth.events import log_finding_candidate
from apps.programs.rate_limit import acquire_for
from apps.targets.models import ScanTarget
```

And at the bottom:

```python
def _emit_finding(
    *, scan_run: "ScanRun", target: "ScanTarget",
    authorization_url: str, confidence: str,
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug="2.15",
        title="OAuth authorization request missing state parameter",
        category="oauth_state_missing",
        severity=Severity.MEDIUM,
        confidence=confidence,
        status=FindingStatus.CANDIDATE,
        data={"authorization_url": authorization_url, "requires_manual_review": True},
    )
    log_finding_candidate(finding, stub_id="2.15")
```

- [ ] **Step 7: Run full test suite for stub 2.15**

```bash
cd backend && python -m pytest apps/stubs/oauth_missing_state/ -v --tb=short
# Expected: all green (gate tests + classify tests + runner tests)
```

- [ ] **Step 8: Check coverage**

```bash
cd backend && python -m pytest apps/stubs/oauth_missing_state/ \
  --cov=apps/stubs/oauth_missing_state --cov-report=term-missing
# Expected: 100% on runner.py and classify.py
```

- [ ] **Step 9: Commit**

```bash
git add backend/apps/stubs/oauth_missing_state/
git commit -m "feat(stubs): 2.15 oauth-missing-state — detection chain"
```
