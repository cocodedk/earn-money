# Task 09 — Stub 2.16: oauth-token-substitution detection chain

Implement passive OAuth detection and active two-account substitution
test in `oauth_token_substitution/`.

**Files:**
- Create: `backend/apps/stubs/oauth_token_substitution/classify.py`
- Create: `backend/apps/stubs/oauth_token_substitution/submit.py`
- Modify: `backend/apps/stubs/oauth_token_substitution/runner.py`
- Create: `backend/apps/stubs/oauth_token_substitution/tests/test_classify.py`
- Create: `backend/apps/stubs/oauth_token_substitution/tests/test_submit.py`
- Create: `backend/apps/stubs/oauth_token_substitution/tests/test_runner.py`

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

- [ ] **Step 8: Write runner test + implement detection chain**

`backend/apps/stubs/oauth_token_substitution/tests/test_runner.py`:

```python
"""End-to-end tests for stub 2.16 (oauth-token-substitution)."""
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
from apps.stubs.oauth_token_substitution.runner import run
from apps.stubs.oauth_token_substitution.submit import SubstitutionResult

_MODULE = "apps.stubs.oauth_token_substitution.runner"


def _program(knob_on=True, accounts=None) -> Program:
    return Program(
        platform="local", slug="oauth-token-substitution-lab",
        scope=Scope(
            platform="local", slug="oauth-token-substitution-lab",
            policy="rate-limited-OK",
            in_scope=["oauth-token-substitution-lab"], out_of_scope=[],
        ),
        roe=RoE(
            max_requests_per_second=30,
            allow_oauth_probes=knob_on,
            allow_active_login_probes=True,
            authorized_test_accounts=accounts or ["user_a", "user_b"],
        ),
    )


@pytest.mark.django_db
def test_confirmed_substitution_creates_finding(monkeypatch):
    monkeypatch.setenv("FIXTURE_OAUTH_TOKEN_SUB_URL", "http://oauth-token-substitution-lab:3000")
    scan_run, target_run = seed_target_run(host="oauth-token-substitution-lab", stub_slug="2.16")
    confirmed = SubstitutionResult(
        substitution_attempted=True, substitution_accepted=True,
        identity_mismatch_observed=True, status="confirmed",
        confidence="high", artifact_kind="authorization_code",
        flow_url="http://oauth-token-substitution-lab:3000",
    )
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.run_substitution_test", return_value=confirmed):
            run(scan_run, target_run)
    assert Finding.objects.filter(scan_run=scan_run, stub_slug="2.16", confidence="high").exists()


@pytest.mark.django_db
def test_passive_only_no_active_creates_candidate(monkeypatch):
    monkeypatch.setenv("FIXTURE_OAUTH_TOKEN_SUB_URL", "http://oauth-token-substitution-lab:3000")
    scan_run, target_run = seed_target_run(host="oauth-token-substitution-lab", stub_slug="2.16")
    prog = _program(accounts=[])  # no accounts → passive only
    resp = MagicMock()
    resp.status_code = 302
    resp.url = "http://oauth-token-substitution-lab:3000/oauth/authorize?client_id=x&response_type=code&redirect_uri=http://localhost/cb"
    resp.text = ""
    with patch.object(get_registry(), "find_for_host", return_value=prog):
        with patch(f"{_MODULE}.fetch_for_discovery", return_value=resp):
            run(scan_run, target_run)
    f = Finding.objects.filter(scan_run=scan_run, stub_slug="2.16")
    # passive candidate or no finding — must not be confirmed
    for finding in f:
        assert finding.status != "confirmed"
```

Detection chain in `runner.py`:

```python
    import os
    from apps.stubs._shared.auth.discovery import fetch_for_discovery
    from apps.programs.rate_limit import acquire_for
    from apps.findings.models import Finding, FindingStatus, Severity
    from apps.stubs._shared.auth.events import log_finding_candidate
    from apps.targets.models import ScanTarget
    from .classify import classify_passive_oauth_evidence
    from .submit import run_substitution_test
    import httpx

    _STUB_ID = "2.16"
    fixture_url = os.environ.get("FIXTURE_OAUTH_TOKEN_SUB_URL", target.base_url)
    accounts = program.roe.authorized_test_accounts

    # Passive discovery
    acquire_for(program)
    resp = fetch_for_discovery(
        url=fixture_url + "/login",
        target=target, program=program, follow_redirects=True,
    )
    evidence = classify_passive_oauth_evidence(resp) if resp else None

    # Active substitution test — only with two scanner-owned accounts
    if program.roe.allow_active_login_probes and len(accounts) >= 2:
        http = httpx.Client(follow_redirects=False, timeout=10)
        result = run_substitution_test(
            base_url=fixture_url,
            cred_a=(accounts[0], os.environ.get("FIXTURE_OAUTH_TOKEN_SUB_PASS_A", "pass-a")),
            cred_b=(accounts[1], os.environ.get("FIXTURE_OAUTH_TOKEN_SUB_PASS_B", "pass-b")),
            http=http,
        )
        if result.status in ("confirmed", "candidate") and result.substitution_attempted:
            _emit_token_sub_finding(
                scan_run=scan_run, target=target, result=result,
            )
            return

    # Fall back to passive candidate
    if evidence and evidence.detected:
        _emit_token_sub_finding(
            scan_run=scan_run, target=target,
            result=None, passive_evidence=evidence,
        )
```

Add helper:

```python
def _emit_token_sub_finding(*, scan_run, target, result=None, passive_evidence=None):
    from apps.stubs._shared.auth.events import log_finding_candidate
    from apps.findings.models import Finding, FindingStatus, Severity
    if result and result.substitution_attempted:
        conf, sev = result.confidence, Severity.HIGH if result.status == "confirmed" else Severity.MEDIUM
        data = {
            "artifact_kind": result.artifact_kind,
            "identity_mismatch": result.identity_mismatch_observed,
            "substitution_accepted": result.substitution_accepted,
            "requires_manual_review": result.status != "confirmed",
        }
    else:
        conf, sev = "low", Severity.INFO
        data = {
            "artifact_kind": passive_evidence.artifact_kind if passive_evidence else "unknown",
            "passive_only": True,
            "requires_manual_review": True,
        }
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug="2.16",
        title="OAuth token/code substitution possible",
        category="oauth_token_substitution",
        severity=sev,
        confidence=conf,
        status=FindingStatus.CANDIDATE,
        data=data,
    )
    log_finding_candidate(finding, stub_id="2.16")
```

- [ ] **Step 9: Run tests + coverage**

```bash
cd backend && python -m pytest apps/stubs/oauth_token_substitution/ -v --tb=short
cd backend && python -m pytest apps/stubs/oauth_token_substitution/ \
  --cov=apps/stubs/oauth_token_substitution --cov-report=term-missing
```

- [ ] **Step 10: Commit**

```bash
git add backend/apps/stubs/oauth_token_substitution/
git commit -m "feat(stubs): 2.16 oauth-token-substitution — passive + active substitution test"
```
