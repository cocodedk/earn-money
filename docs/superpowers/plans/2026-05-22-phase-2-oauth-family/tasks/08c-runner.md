# Task 08c — Stub 2.14: runner integration tests (test_runner.py)

**Part of:** Task 08 — Stub 2.14: oauth-redirect-uri detection chain

**Files:**
- Create: `backend/apps/stubs/oauth_redirect_uri/tests/test_runner.py`

**Continues from:** [08b-classify.md](08b-classify.md)

**Continues in:** [08d-runner-impl.md](08d-runner-impl.md)

---

- [ ] **Step 9a: Write runner integration tests**

`backend/apps/stubs/oauth_redirect_uri/tests/test_runner.py`:

```python
"""End-to-end detection tests for stub 2.14 (oauth-redirect-uri)."""
from __future__ import annotations
import json
from unittest.mock import MagicMock, patch
import pytest
from apps.events.models import Event
from apps.events.types import EventType
from apps.findings.models import Finding
from apps.programs.loader import Program, get_registry
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._shared.auth.discovery import FetchOutcome
from apps.stubs._test_factories import seed_target_run
from apps.stubs.oauth_redirect_uri.runner import run

_MODULE = "apps.stubs.oauth_redirect_uri.runner"
_BASE = "http://oauth-redirect-uri-lab:3000"


def _program(knob_on: bool = True) -> Program:
    return Program(
        platform="local", slug="oauth-redirect-uri-lab",
        scope=Scope(
            platform="local", slug="oauth-redirect-uri-lab",
            policy="rate-limited-OK",
            in_scope=["oauth-redirect-uri-lab"], out_of_scope=[],
        ),
        roe=RoE(
            max_requests_per_second=30,
            allow_oauth_probes=knob_on,
            authorized_test_accounts=["scanner@example.invalid"],
        ),
    )


def _oidc_outcome():
    body = json.dumps({
        "authorization_endpoint": f"{_BASE}/oauth/authorize/strict",
        "authorization_endpoint_variants": [
            f"{_BASE}/oauth/authorize/foreign-origin",
            f"{_BASE}/oauth/authorize/preserves-invalid",
        ],
        "issuer": _BASE,
    })
    return FetchOutcome(
        ok=True, status=200, body=body,
        content_type="application/json",
        final_url=f"{_BASE}/.well-known/openid-configuration",
        error=None,
    )


def _confirmed_response():
    r = MagicMock()
    r.status_code = 302
    r.headers = {"Location": "https://scanner.invalid/oauth-callback?code=x"}
    r.text = ""
    return r


def _rejected_response():
    r = MagicMock()
    r.status_code = 400
    r.headers = {}
    r.text = '{"error":"invalid_redirect_uri"}'
    return r


@pytest.mark.django_db
def test_confirmed_redirect_creates_finding(monkeypatch):
    monkeypatch.setenv("FIXTURE_OAUTH_REDIRECT_URI_URL", _BASE)
    monkeypatch.setenv("FIXTURE_OAUTH_CLIENT_SECRET", "fixture-value")
    scan_run, target_run = seed_target_run(host="oauth-redirect-uri-lab", stub_slug="2.14")
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.fetch_for_discovery", return_value=_oidc_outcome()):
            with patch(f"{_MODULE}.submit_probe", return_value=_confirmed_response()):
                run(scan_run, target_run)
    assert Finding.objects.filter(scan_run=scan_run, stub_slug="2.14",
                                   confidence="high").exists()


@pytest.mark.django_db
def test_strict_rejection_no_finding(monkeypatch):
    monkeypatch.setenv("FIXTURE_OAUTH_REDIRECT_URI_URL", _BASE)
    monkeypatch.setenv("FIXTURE_OAUTH_CLIENT_SECRET", "fixture-value")
    scan_run, target_run = seed_target_run(host="oauth-redirect-uri-lab", stub_slug="2.14")
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.fetch_for_discovery", return_value=_oidc_outcome()):
            with patch(f"{_MODULE}.submit_probe", return_value=_rejected_response()):
                run(scan_run, target_run)
    assert not Finding.objects.filter(scan_run=scan_run, stub_slug="2.14",
                                       confidence="high").exists()


@pytest.mark.django_db
def test_oidc_discovery_failure_emits_refusal(monkeypatch):
    monkeypatch.setenv("FIXTURE_OAUTH_REDIRECT_URI_URL", _BASE)
    monkeypatch.setenv("FIXTURE_OAUTH_CLIENT_SECRET", "fixture-value")
    scan_run, target_run = seed_target_run(host="oauth-redirect-uri-lab", stub_slug="2.14")
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.fetch_for_discovery",
                   return_value=FetchOutcome(ok=False, status=0, body="",
                                             content_type="", final_url="",
                                             error="connect_error")):
            run(scan_run, target_run)
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    ).exists()
```

**Continues in:** [08d-runner-impl.md](08d-runner-impl.md)
