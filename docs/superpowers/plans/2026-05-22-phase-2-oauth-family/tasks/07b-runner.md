# Task 07b — Stub 2.15: wire detection chain into `runner.py`

Add the integration tests and detection logic to the runner. Continues from classify work.

**Files:** `runner.py` (modify), `tests/test_runner.py` (create)
**Continues from:** [07a-classify.md](07a-classify.md)

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
            authorized_test_accounts=["scanner@example.invalid"],
        ),
    )


def _redirect_response(location: str, status: int = 302):
    r = MagicMock()
    r.status_code = status
    r.headers = {"Location": location} if location else {}
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
        with patch(f"{_MODULE}.submit_probe",
                   return_value=_redirect_response(vuln_location)):
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
        with patch(f"{_MODULE}.submit_probe",
                   return_value=_redirect_response(safe_location)):
            run(scan_run, target_run)

    assert not Finding.objects.filter(scan_run=scan_run, stub_slug="2.15").exists()


@pytest.mark.django_db
def test_non_oauth_redirect_no_finding(monkeypatch):
    monkeypatch.setenv("FIXTURE_OAUTH_CLIENT_SECRET", "fixture-value")
    scan_run, target_run = seed_target_run(host="oauth-state-missing", stub_slug="2.15")
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.submit_probe",
                   return_value=_redirect_response("http://oauth-state-missing:3000/login")):
            run(scan_run, target_run)

    assert not Finding.objects.filter(scan_run=scan_run, stub_slug="2.15").exists()


@pytest.mark.django_db
def test_transport_error_emits_refusal(monkeypatch):
    monkeypatch.setenv("FIXTURE_OAUTH_CLIENT_SECRET", "fixture-value")
    scan_run, target_run = seed_target_run(host="oauth-state-missing", stub_slug="2.15")
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.submit_probe", return_value=None):
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
    # Missing-state detection must inspect the first 302 Location; do not follow redirects.
    request = httpx.Request("GET", fixture_url.rstrip("/") + "/auth/example")
    resp = submit_probe(request)
    if resp is None:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id="2.15",
            reason=RefusalReason.TRANSPORT_ERROR,
            details={"detail": "target_unreachable"},
        )
        return

    authorization_url = resp.headers.get("Location", "")
    if not authorization_url:
        return
    authorization_url = urljoin(fixture_url.rstrip("/") + "/", authorization_url)

    from .classify import inspect_authorization_url
    inspection = inspect_authorization_url(authorization_url)
    if not inspection.is_oauth_authorization_request or inspection.has_state:
        return

    _emit_finding(
        scan_run=scan_run, target=target,
        authorization_url=authorization_url,
        confidence=inspection.confidence,
    )
```
Add imports at top of `runner.py`:
```python
import os
from urllib.parse import urljoin
import httpx
from apps.findings.models import Finding, FindingStatus, Severity
from apps.stubs._shared.auth.requests import submit_probe
from apps.stubs._shared.auth.events import log_finding_candidate
from apps.programs.rate_limit import acquire_for
from apps.targets.models import ScanTarget
```
Add `_emit_finding` at the bottom:
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
