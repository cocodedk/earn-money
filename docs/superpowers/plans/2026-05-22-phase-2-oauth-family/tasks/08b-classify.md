# Task 08b — Stub 2.14: response classification (test_classify.py + classify.py)

**Part of:** Task 08 — Stub 2.14: oauth-redirect-uri detection chain

**Files:**
- Create: `backend/apps/stubs/oauth_redirect_uri/tests/test_classify.py`
- Create: `backend/apps/stubs/oauth_redirect_uri/classify.py`

**Continues from:** [08a-mutate.md](08a-mutate.md)

**Continues in:** [08c-runner.md](08c-runner.md)

---

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

**Continues in:** [08c-runner.md](08c-runner.md)
