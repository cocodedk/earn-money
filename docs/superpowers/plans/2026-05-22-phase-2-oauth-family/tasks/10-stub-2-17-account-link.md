# Task 10 — Stub 2.17: oauth-account-linking detection chain

Implement passive discovery, classification, and fixture-mode active
checks in `oauth_account_linking/`.

**Files:**
- Create: `backend/apps/stubs/oauth_account_linking/classify.py`
- Modify: `backend/apps/stubs/oauth_account_linking/runner.py`
- Create: `backend/apps/stubs/oauth_account_linking/tests/test_classify.py`
- Create: `backend/apps/stubs/oauth_account_linking/tests/test_runner.py`

**Depends on:** Task 05, Task 06

---

- [ ] **Step 1: Write failing tests for `classify.py`**

`backend/apps/stubs/oauth_account_linking/tests/test_classify.py`:

```python
"""Unit tests for stub 2.17 account-linking flaw classification."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest
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
    headers: dict = getattr(response, "headers", {})

    parsed_url = urlparse(endpoint_url)
    path_lower = parsed_url.path.lower()

    # Detect link-related endpoint
    is_link_path = any(h in path_lower for h in _LINK_PATH_HINTS)

    # GET link action — state-changing GET
    if method == "GET" and is_link_path and status_code == 200 and "linked" in body.lower():
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
    if method == "POST" and no_csrf_sent and status_code == 200 and "linked" in body.lower():
        return LinkFlawClassification(
            kind=AccountLinkingFlawKind.MISSING_CSRF_ON_LINK,
            endpoint_url=endpoint_url, http_method=method,
            confidence="medium", status="candidate",
        )

    return None
```

- [ ] **Step 4: Run classify tests — verify PASS**

```bash
cd backend && python -m pytest apps/stubs/oauth_account_linking/tests/test_classify.py -v
```

- [ ] **Step 5: Write runner tests + detection chain**

`backend/apps/stubs/oauth_account_linking/tests/test_runner.py`:

```python
"""End-to-end tests for stub 2.17 (oauth-account-linking)."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest
from apps.findings.models import Finding
from apps.events.models import Event
from apps.events.types import EventType
from apps.programs.loader import Program, get_registry
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._test_factories import seed_target_run
from apps.stubs.oauth_account_linking.runner import run

_MODULE = "apps.stubs.oauth_account_linking.runner"


def _program(knob_on=True, accounts=None) -> Program:
    return Program(
        platform="local", slug="oauth-account-linking-lab",
        scope=Scope(
            platform="local", slug="oauth-account-linking-lab",
            policy="rate-limited-OK",
            in_scope=["oauth-account-linking-lab"], out_of_scope=[],
        ),
        roe=RoE(
            max_requests_per_second=30,
            allow_oauth_probes=knob_on,
            allow_active_login_probes=True,
            authorized_test_accounts=accounts or ["user_a"],
        ),
    )


def _link_redirect_response():
    r = MagicMock()
    r.status_code = 302
    r.request = MagicMock()
    r.request.method = "GET"
    r.url = "http://oauth-account-linking-lab:3000/auth/link/start"
    r.text = ""
    r.headers = {
        "Location": "http://oauth-account-linking-lab:3000/oauth/authorize-mock"
                    "?client_id=link-client&response_type=code&redirect_uri=http://localhost/cb"
    }
    return r


def _no_oauth_response():
    r = MagicMock()
    r.status_code = 200
    r.request = MagicMock()
    r.request.method = "GET"
    r.url = "http://oauth-account-linking-lab:3000/settings/connections"
    r.text = '{"linkedProviders":[]}'
    r.headers = {}
    return r


@pytest.mark.django_db
def test_missing_state_creates_finding(monkeypatch):
    monkeypatch.setenv("FIXTURE_OAUTH_ACCOUNT_LINK_URL", "http://oauth-account-linking-lab:3000")
    scan_run, target_run = seed_target_run(host="oauth-account-linking-lab", stub_slug="2.17")
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.fetch_for_discovery", return_value=_link_redirect_response()):
            run(scan_run, target_run)
    assert Finding.objects.filter(scan_run=scan_run, stub_slug="2.17").exists()


@pytest.mark.django_db
def test_no_link_ui_no_finding(monkeypatch):
    monkeypatch.setenv("FIXTURE_OAUTH_ACCOUNT_LINK_URL", "http://oauth-account-linking-lab:3000")
    scan_run, target_run = seed_target_run(host="oauth-account-linking-lab", stub_slug="2.17")
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.fetch_for_discovery", return_value=_no_oauth_response()):
            run(scan_run, target_run)
    assert not Finding.objects.filter(scan_run=scan_run, stub_slug="2.17").exists()


@pytest.mark.django_db
def test_transport_error_emits_refusal(monkeypatch):
    monkeypatch.setenv("FIXTURE_OAUTH_ACCOUNT_LINK_URL", "http://oauth-account-linking-lab:3000")
    scan_run, target_run = seed_target_run(host="oauth-account-linking-lab", stub_slug="2.17")
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.fetch_for_discovery", return_value=None):
            run(scan_run, target_run)
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    ).exists()
```

Detection chain in `runner.py` — replace `return` with:

```python
    import os
    from apps.stubs._shared.auth.discovery import fetch_for_discovery
    from apps.programs.rate_limit import acquire_for
    from apps.findings.models import Finding, FindingStatus, Severity
    from apps.stubs._shared.auth.events import log_finding_candidate
    from apps.targets.models import ScanTarget
    from .classify import classify_link_flaw

    _STUB_ID = "2.17"
    fixture_url = os.environ.get("FIXTURE_OAUTH_ACCOUNT_LINK_URL", target.base_url)

    _CANDIDATE_PATHS = [
        "/auth/link/start",
        "/settings/connections/link/mock",
        "/settings/connections",
    ]

    for path in _CANDIDATE_PATHS:
        acquire_for(program)
        resp = fetch_for_discovery(
            url=fixture_url + path,
            target=target, program=program, follow_redirects=False,
        )
        if resp is None:
            record_refusal(
                scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
                reason=RefusalReason.TRANSPORT_ERROR,
                details={"detail": f"target_unreachable:{path}"},
            )
            return

        flaw = classify_link_flaw(resp, endpoint_url=fixture_url + path)
        if flaw is not None:
            _emit_link_finding(
                scan_run=scan_run, target=target, flaw=flaw,
            )
            return
```

Add helper:

```python
def _emit_link_finding(*, scan_run, target, flaw) -> None:
    from apps.findings.models import Finding, FindingStatus, Severity
    from apps.stubs._shared.auth.events import log_finding_candidate
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug="2.17",
        title=f"Account-linking flaw: {flaw.kind.value}",
        category="oauth_account_linking_flaws",
        severity=Severity.MEDIUM,
        confidence=flaw.confidence,
        status=FindingStatus.CANDIDATE,
        data={
            "kind": flaw.kind.value,
            "endpoint": flaw.endpoint_url,
            "method": flaw.http_method,
            "requires_manual_review": True,
        },
    )
    log_finding_candidate(finding, stub_id="2.17")
```

- [ ] **Step 6: Run tests + coverage**

```bash
cd backend && python -m pytest apps/stubs/oauth_account_linking/ -v --tb=short
cd backend && python -m pytest apps/stubs/oauth_account_linking/ \
  --cov=apps/stubs/oauth_account_linking --cov-report=term-missing
```

- [ ] **Step 7: Commit**

```bash
git add backend/apps/stubs/oauth_account_linking/
git commit -m "feat(stubs): 2.17 oauth-account-linking — passive discovery + classify"
```

---

## After Task 10

Run `/codex-review` on the complete OAuth family (stubs 2.14–2.17 +
fixture), then iterate `/code-review high` until clean.

Update cookbook spec frontmatter for 2.14–2.17 to `status: done`.

Run `scripts/cookbook_progress.py` to regenerate `PROGRESS.md`.

Commit: `docs(progress): Phase 2 OAuth family 2.14-2.17 done`.
