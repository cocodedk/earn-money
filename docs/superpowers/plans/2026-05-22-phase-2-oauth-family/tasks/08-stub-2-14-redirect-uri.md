# Task 08 — Stub 2.14: oauth-redirect-uri detection chain

Implement mutation generation, outcome classification, and the
detection chain in `oauth_redirect_uri/`.

**Files:**
- Create: `backend/apps/stubs/oauth_redirect_uri/mutate.py`
- Create: `backend/apps/stubs/oauth_redirect_uri/classify.py`
- Modify: `backend/apps/stubs/oauth_redirect_uri/runner.py`
- Create: `backend/apps/stubs/oauth_redirect_uri/tests/test_mutate.py`
- Create: `backend/apps/stubs/oauth_redirect_uri/tests/test_classify.py`
- Create: `backend/apps/stubs/oauth_redirect_uri/tests/test_runner.py`

**Depends on:** Task 03, Task 06

---

- [ ] **Step 1: Write failing tests for `mutate.py`**

`backend/apps/stubs/oauth_redirect_uri/tests/test_mutate.py`:

```python
"""Unit tests for stub 2.14 redirect URI mutation generation."""
from __future__ import annotations
import pytest
from apps.stubs.oauth_redirect_uri.mutate import generate_mutations, MutationClass


VALID = "https://app.example.test/oauth/callback"
SCANNER = "https://scanner.invalid"


def test_generates_all_mutation_classes():
    mutations = generate_mutations(VALID, SCANNER)
    classes = {m.mutation_class for m in mutations}
    assert MutationClass.FOREIGN_ORIGIN in classes
    assert MutationClass.HOST_SUFFIX in classes
    assert MutationClass.HOST_PREFIX in classes
    assert MutationClass.SCHEME_DOWNGRADE in classes
    assert MutationClass.PATH_PREFIX in classes
    assert MutationClass.PATH_TRAVERSAL in classes
    assert MutationClass.ENCODED_HOST in classes
    assert MutationClass.USERINFO_CONFUSION in classes


def test_count_respects_cap():
    mutations = generate_mutations(VALID, SCANNER, max_probes=4)
    assert len(mutations) <= 4


def test_foreign_origin_uses_scanner_origin():
    mutations = generate_mutations(VALID, SCANNER)
    foreign = next(m for m in mutations if m.mutation_class == MutationClass.FOREIGN_ORIGIN)
    from urllib.parse import urlparse
    assert urlparse(foreign.mutated_uri).netloc == "scanner.invalid"


def test_scheme_downgrade_uses_http():
    mutations = generate_mutations(VALID, SCANNER)
    downgrade = next(m for m in mutations if m.mutation_class == MutationClass.SCHEME_DOWNGRADE)
    assert downgrade.mutated_uri.startswith("http://")


def test_mutations_preserve_state():
    mutations = generate_mutations(VALID, SCANNER)
    for m in mutations:
        assert m.mutation_class is not None
        assert m.mutated_uri


def test_invalid_baseline_returns_empty():
    mutations = generate_mutations("not-a-url", SCANNER)
    assert mutations == []
```

- [ ] **Step 2: Run — verify FAIL**

```bash
cd backend && python -m pytest apps/stubs/oauth_redirect_uri/tests/test_mutate.py -v 2>&1 | grep -E "FAILED|ERROR|ImportError"
```

- [ ] **Step 3: Write `mutate.py`**

```python
"""Stub 2.14 — redirect URI mutation generation."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal
from urllib.parse import urlparse, quote


class MutationClass(str, Enum):
    FOREIGN_ORIGIN = "foreign_origin"
    HOST_SUFFIX = "host_suffix"
    HOST_PREFIX = "host_prefix"
    SCHEME_DOWNGRADE = "scheme_downgrade"
    PATH_PREFIX = "path_prefix"
    PATH_TRAVERSAL = "path_traversal"
    ENCODED_HOST = "encoded_host"
    USERINFO_CONFUSION = "userinfo_confusion"


@dataclass(frozen=True)
class RedirectUriMutation:
    mutation_class: MutationClass
    mutated_uri: str
    baseline_uri: str
    scanner_origin: str


def generate_mutations(
    baseline_redirect_uri: str,
    scanner_origin: str,
    max_probes: int = 8,
) -> list[RedirectUriMutation]:
    """Generate at most `max_probes` mutated redirect URIs from `baseline_redirect_uri`."""
    try:
        b = urlparse(baseline_redirect_uri)
        s = urlparse(scanner_origin)
    except Exception:
        return []

    if not b.netloc or not s.netloc:
        return []

    scanner_host = s.netloc
    trusted_host = b.netloc
    trusted_path = b.path or "/oauth/callback"

    candidates: list[tuple[MutationClass, str]] = [
        (MutationClass.FOREIGN_ORIGIN,
         f"{scanner_origin}{trusted_path}"),
        (MutationClass.HOST_SUFFIX,
         f"{b.scheme}://{trusted_host}.{scanner_host}{trusted_path}"),
        (MutationClass.HOST_PREFIX,
         f"{b.scheme}://{scanner_host}/{trusted_host}{trusted_path}"),
        (MutationClass.SCHEME_DOWNGRADE,
         f"http://{trusted_host}{trusted_path}"),
        (MutationClass.PATH_PREFIX,
         f"{b.scheme}://{trusted_host}{trusted_path}.evil"),
        (MutationClass.PATH_TRAVERSAL,
         f"{b.scheme}://{trusted_host}{trusted_path}/../evil"),
        (MutationClass.ENCODED_HOST,
         f"{b.scheme}://{trusted_host.replace('.', '%2e')}.{scanner_host}{trusted_path}"),
        (MutationClass.USERINFO_CONFUSION,
         f"{b.scheme}://{trusted_host}@{scanner_host}{trusted_path}"),
    ]

    return [
        RedirectUriMutation(
            mutation_class=cls,
            mutated_uri=uri,
            baseline_uri=baseline_redirect_uri,
            scanner_origin=scanner_origin,
        )
        for cls, uri in candidates[:max_probes]
    ]
```

- [ ] **Step 4: Run mutate tests — verify PASS**

```bash
cd backend && python -m pytest apps/stubs/oauth_redirect_uri/tests/test_mutate.py -v
```

- [ ] **Step 5: Write failing tests for `classify.py`**

`backend/apps/stubs/oauth_redirect_uri/tests/test_classify.py`:

```python
"""Unit tests for stub 2.14 redirect URI outcome classification."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest
from apps.stubs.oauth_redirect_uri.classify import (
    classify_redirect_response, ValidationResult,
)

SCANNER = "https://scanner.invalid"


def _resp(status: int, location: str = "", body: str = "", content_type: str = "text/html"):
    r = MagicMock()
    r.status_code = status
    r.headers = {"Location": location} if location else {}
    r.text = body
    r.headers.get = lambda k, d="": {"Location": location}.get(k, d) if location else d
    return r


def test_3xx_to_scanner_origin_is_confirmed():
    resp = _resp(302, f"{SCANNER}/oauth-callback?code=x")
    result = classify_redirect_response(resp, SCANNER)
    assert result.validation_result == ValidationResult.ACCEPTED_UNTRUSTED_REDIRECT
    assert result.confidence == "high"
    assert result.status == "confirmed"


def test_4xx_with_invalid_redirect_uri_error_is_rejected():
    resp = _resp(400, body='{"error":"invalid_redirect_uri"}', content_type="application/json")
    result = classify_redirect_response(resp, SCANNER)
    assert result.validation_result == ValidationResult.REJECTED_INVALID_REDIRECT
    assert result.status == "rejected"
    assert result.confidence == "high"


def test_login_page_with_redirect_uri_in_hidden_field_is_candidate():
    body = '<form><input type="hidden" name="redirect_uri" value="https://scanner.invalid/cb"></form>'
    resp = _resp(200, body=body)
    result = classify_redirect_response(resp, SCANNER)
    assert result.validation_result == ValidationResult.PRESERVED_UNTRUSTED_REDIRECT
    assert result.status == "candidate"


def test_login_page_without_scanner_uri_is_not_vulnerable():
    resp = _resp(200, body="<form><input type='text' name='username'></form>")
    result = classify_redirect_response(resp, SCANNER)
    assert result.status in ("rejected", "candidate")
    assert result.validation_result != ValidationResult.ACCEPTED_UNTRUSTED_REDIRECT


def test_uses_url_parser_not_string_match():
    # Origin comparison must use parsed URL, not substring
    resp = _resp(302, "https://scanner.invalid.trusted.example/cb?code=x")
    result = classify_redirect_response(resp, SCANNER)
    # scanner.invalid.trusted.example origin != scanner.invalid
    assert result.status != "confirmed"
```

- [ ] **Step 6: Run classify tests — verify FAIL**

```bash
cd backend && python -m pytest apps/stubs/oauth_redirect_uri/tests/test_classify.py -v 2>&1 | grep -E "FAILED|ERROR|ImportError"
```

- [ ] **Step 7: Write `classify.py`**

```python
"""Stub 2.14 — redirect URI outcome classification."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal
from urllib.parse import urlparse


class ValidationResult(str, Enum):
    ACCEPTED_UNTRUSTED_REDIRECT = "accepted_untrusted_redirect"
    PRESERVED_UNTRUSTED_REDIRECT = "preserved_untrusted_redirect"
    REJECTED_INVALID_REDIRECT = "rejected_invalid_redirect"
    NOT_TESTED = "not_tested"
    INCONCLUSIVE = "inconclusive"


_REJECT_PHRASES = frozenset({
    "invalid_redirect_uri", "redirect_uri_mismatch",
    "invalid_request", "unauthorized_client",
})


@dataclass(frozen=True)
class RedirectUriClassification:
    validation_result: ValidationResult
    status: Literal["confirmed", "candidate", "rejected", "stale"]
    confidence: Literal["low", "medium", "high"]
    location_origin: str | None
    oauth_error: str | None


def classify_redirect_response(
    response: object,
    scanner_origin: str,
) -> RedirectUriClassification:
    """Classify a pre-auth authorization response against a mutated redirect URI."""
    status_code: int = getattr(response, "status_code", 0)
    headers: dict = getattr(response, "headers", {})
    body: str = getattr(response, "text", "") or ""

    scanner_parsed = urlparse(scanner_origin)

    # 3xx — check if Location points to scanner origin
    if 300 <= status_code < 400:
        location = headers.get("Location", "")
        if location:
            loc_parsed = urlparse(location)
            loc_origin = f"{loc_parsed.scheme}://{loc_parsed.netloc}"
            scanner_origin_norm = f"{scanner_parsed.scheme}://{scanner_parsed.netloc}"
            if loc_origin == scanner_origin_norm:
                return RedirectUriClassification(
                    validation_result=ValidationResult.ACCEPTED_UNTRUSTED_REDIRECT,
                    status="confirmed", confidence="high",
                    location_origin=loc_parsed.netloc, oauth_error=None,
                )

    # 4xx — look for OAuth error phrases
    if status_code in (400, 401, 403):
        error = _extract_oauth_error(body, headers)
        if error and any(p in error for p in _REJECT_PHRASES):
            return RedirectUriClassification(
                validation_result=ValidationResult.REJECTED_INVALID_REDIRECT,
                status="rejected",
                confidence="high",
                location_origin=None,
                oauth_error=error,
            )

    # 200 — check if scanner URI appears in hidden field or form action
    if status_code == 200 and scanner_origin in body:
        return RedirectUriClassification(
            validation_result=ValidationResult.PRESERVED_UNTRUSTED_REDIRECT,
            status="candidate",
            confidence="medium",
            location_origin=None,
            oauth_error=None,
        )

    return RedirectUriClassification(
        validation_result=ValidationResult.INCONCLUSIVE,
        status="rejected",
        confidence="low",
        location_origin=None,
        oauth_error=None,
    )


def _extract_oauth_error(body: str, headers: dict) -> str | None:
    import json
    try:
        return json.loads(body).get("error", "")
    except Exception:
        pass
    for phrase in _REJECT_PHRASES:
        if phrase in body:
            return phrase
    return None
```

- [ ] **Step 8: Run classify tests — verify PASS**

```bash
cd backend && python -m pytest apps/stubs/oauth_redirect_uri/tests/test_classify.py -v
```

- [ ] **Step 9: Write runner integration tests + implement detection chain in `runner.py`**

`backend/apps/stubs/oauth_redirect_uri/tests/test_runner.py`:

```python
"""End-to-end detection tests for stub 2.14 (oauth-redirect-uri)."""
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
from apps.stubs.oauth_redirect_uri.runner import run

_MODULE = "apps.stubs.oauth_redirect_uri.runner"


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
            authorized_test_accounts=[],
        ),
    )


def _oidc_response():
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {
        "authorization_endpoint": "http://oauth-redirect-uri-lab:3000/oauth/authorize/strict",
        "issuer": "http://oauth-redirect-uri-lab:3000",
    }
    return r


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
    monkeypatch.setenv("FIXTURE_OAUTH_REDIRECT_URI_URL", "http://oauth-redirect-uri-lab:3000")
    scan_run, target_run = seed_target_run(host="oauth-redirect-uri-lab", stub_slug="2.14")
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.fetch_for_discovery", side_effect=[_oidc_response()]):
            with patch(f"{_MODULE}.submit_probe", return_value=_confirmed_response()):
                run(scan_run, target_run)
    assert Finding.objects.filter(scan_run=scan_run, stub_slug="2.14",
                                   confidence="high").exists()


@pytest.mark.django_db
def test_strict_rejection_no_finding(monkeypatch):
    monkeypatch.setenv("FIXTURE_OAUTH_REDIRECT_URI_URL", "http://oauth-redirect-uri-lab:3000")
    scan_run, target_run = seed_target_run(host="oauth-redirect-uri-lab", stub_slug="2.14")
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.fetch_for_discovery", side_effect=[_oidc_response()]):
            with patch(f"{_MODULE}.submit_probe", return_value=_rejected_response()):
                run(scan_run, target_run)
    assert not Finding.objects.filter(scan_run=scan_run, stub_slug="2.14",
                                       confidence="high").exists()


@pytest.mark.django_db
def test_oidc_discovery_failure_emits_refusal(monkeypatch):
    monkeypatch.setenv("FIXTURE_OAUTH_REDIRECT_URI_URL", "http://oauth-redirect-uri-lab:3000")
    scan_run, target_run = seed_target_run(host="oauth-redirect-uri-lab", stub_slug="2.14")
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.fetch_for_discovery", return_value=None):
            run(scan_run, target_run)
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    ).exists()
```

Detection chain in `runner.py` — replace `return` placeholder at end with:

```python
    import os
    from apps.stubs._shared.auth.discovery import fetch_for_discovery
    from apps.stubs._shared.auth.requests import submit_probe
    from apps.programs.rate_limit import acquire_for
    from apps.findings.models import Finding, FindingStatus, Severity
    from apps.stubs._shared.auth.events import log_finding_candidate
    from apps.targets.models import ScanTarget
    from .mutate import generate_mutations
    from .classify import classify_redirect_response, ValidationResult

    _STUB_ID = "2.14"
    _SCANNER_ORIGIN = os.environ.get("SCANNER_REDIRECT_ORIGIN", "https://scanner.invalid")
    fixture_url = os.environ.get("FIXTURE_OAUTH_REDIRECT_URI_URL", target.base_url)

    # OIDC discovery
    acquire_for(program)
    oidc_resp = fetch_for_discovery(
        url=fixture_url + "/.well-known/openid-configuration",
        target=target, program=program, follow_redirects=False,
    )
    if oidc_resp is None:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.TRANSPORT_ERROR,
            details={"detail": "oidc_discovery_unreachable"},
        )
        return

    try:
        auth_endpoint = oidc_resp.json().get("authorization_endpoint", "")
    except Exception:
        return

    if not auth_endpoint:
        return

    # Baseline redirect URI from OIDC doc or config default
    baseline_redirect = os.environ.get(
        "FIXTURE_OAUTH_KNOWN_REDIRECT_URI",
        "https://app.example.test/oauth/callback",
    )
    client_id = os.environ.get("FIXTURE_OAUTH_CLIENT_ID", "test-client")

    mutations = generate_mutations(
        baseline_redirect_uri=baseline_redirect,
        scanner_origin=_SCANNER_ORIGIN,
        max_probes=8,
    )

    for mutation in mutations:
        acquire_for(program)
        resp = submit_probe(
            url=auth_endpoint,
            params={
                "client_id": client_id,
                "redirect_uri": mutation.mutated_uri,
                "response_type": "code",
                "state": secrets.token_hex(8),
            },
            method="GET",
            follow_redirects=False,
        )
        if resp is None:
            continue
        classification = classify_redirect_response(resp, _SCANNER_ORIGIN)
        if classification.status == "confirmed":
            _emit_finding_redirect(
                scan_run=scan_run, target=target,
                auth_endpoint=auth_endpoint,
                mutation_class=mutation.mutation_class.value,
                classification=classification,
            )
            return  # One confirmed finding per endpoint is enough
```

Add helper at bottom of `runner.py`:

```python
def _emit_finding_redirect(
    *, scan_run, target, auth_endpoint, mutation_class, classification,
) -> None:
    from apps.stubs._shared.auth.events import log_finding_candidate
    from apps.findings.models import Finding, FindingStatus, Severity
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug="2.14",
        title="OAuth redirect URI validation weakness",
        category="oauth_redirect_uri_issues",
        severity=Severity.HIGH,
        confidence=classification.confidence,
        status=FindingStatus.CANDIDATE,
        data={
            "auth_endpoint": auth_endpoint,
            "mutation_class": mutation_class,
            "location_origin": classification.location_origin,
            "requires_manual_review": True,
        },
    )
    log_finding_candidate(finding, stub_id="2.14")
```

- [ ] **Step 10: Run full test suite and coverage**

```bash
cd backend && python -m pytest apps/stubs/oauth_redirect_uri/ -v --tb=short
cd backend && python -m pytest apps/stubs/oauth_redirect_uri/ \
  --cov=apps/stubs/oauth_redirect_uri --cov-report=term-missing
# Expected: 100% coverage
```

- [ ] **Step 11: Commit**

```bash
git add backend/apps/stubs/oauth_redirect_uri/
git commit -m "feat(stubs): 2.14 oauth-redirect-uri — mutation + classification + detection chain"
```
