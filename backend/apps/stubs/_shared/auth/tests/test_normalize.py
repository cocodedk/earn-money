"""Contract tests for `_shared/auth/normalize`.

The normalizer strips dynamic values from a response so two probes
against the same endpoint can be compared without false positives
on CSRF / session / nonce / timestamp differences.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from apps.stubs._shared.auth.normalize import (
    Differentiator,
    NormalizedResponse,
    classify_abort,
    diff,
    normalize,
)
from apps.stubs._shared.auth.safety import AbortSignal


def _resp(
    *,
    status: int = 200,
    url: str = "https://example.invalid/login",
    headers: dict | None = None,
    text: str = "",
    content_type: str = "text/html",
) -> MagicMock:
    """Lightweight httpx.Response stand-in for tests."""
    r = MagicMock()
    r.status_code = status
    r.url = url
    r.headers = headers or {"content-type": content_type}
    r.text = text
    return r


# ----- normalize basics ---------------------------------------------

def test_status_and_url_captured() -> None:
    out = normalize(_resp(status=401, url="https://x.test/login"))
    assert out.status == 401
    assert out.final_url == "https://x.test/login"


def test_redirect_location_captured() -> None:
    out = normalize(_resp(
        status=302,
        headers={"content-type": "text/html", "location": "/mfa"},
    ))
    assert out.redirect_location == "/mfa"


def test_title_captured_from_html() -> None:
    out = normalize(_resp(
        text="<html><head><title>Sign in</title></head><body></body></html>",
    ))
    assert out.title == "Sign in"


def test_no_title_for_non_html() -> None:
    out = normalize(_resp(
        text='{"error": "no"}', content_type="application/json",
    ))
    assert out.title is None


def test_json_error_code_captured() -> None:
    out = normalize(_resp(
        text='{"error_code": "USER_NOT_FOUND"}',
        content_type="application/json",
    ))
    assert out.json_error_code == "USER_NOT_FOUND"


def test_json_field_errors_captured() -> None:
    out = normalize(_resp(
        text='{"errors": {"email": "not found", "captcha": "required"}}',
        content_type="application/json",
    ))
    assert out.json_error_fields == {
        "email": "not found", "captcha": "required",
    }


# ----- normalize stripping (the diff invariant) ---------------------

def test_csrf_hidden_input_value_stripped_from_fingerprint() -> None:
    """Two responses with different CSRF tokens hash to the same
    body_fingerprint after normalization."""
    a = normalize(_resp(text=(
        '<html><body><form>'
        '<input type="hidden" name="csrfmiddlewaretoken" value="A123">'
        '<input name="email">'
        '</form></body></html>'
    )))
    b = normalize(_resp(text=(
        '<html><body><form>'
        '<input type="hidden" name="csrfmiddlewaretoken" value="ZZZZ">'
        '<input name="email">'
        '</form></body></html>'
    )))
    assert a.body_fingerprint == b.body_fingerprint


def test_uuid_in_body_stripped() -> None:
    """Random UUIDs in the body don't change the fingerprint."""
    a = normalize(_resp(text="request id: 11111111-2222-3333-4444-555555555555"))
    b = normalize(_resp(text="request id: aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"))
    assert a.body_fingerprint == b.body_fingerprint


def test_session_cookie_value_stripped_from_headers() -> None:
    """Set-Cookie values differ between requests but must not register
    as a differentiator after normalization."""
    a = _resp(headers={
        "content-type": "text/html",
        "set-cookie": "session=abc; Path=/",
    })
    b = _resp(headers={
        "content-type": "text/html",
        "set-cookie": "session=xyz; Path=/",
    })
    assert diff(normalize(a), normalize(b)) == []


# ----- diff semantics -----------------------------------------------

def test_identical_responses_have_empty_diff() -> None:
    a = normalize(_resp(status=200, text="<html><body>hi</body></html>"))
    b = normalize(_resp(status=200, text="<html><body>hi</body></html>"))
    assert diff(a, b) == []


def test_status_diff_reported() -> None:
    a = normalize(_resp(status=401))
    b = normalize(_resp(status=404))
    out = diff(a, b)
    assert any(d.kind == "status_code" for d in out)


def test_redirect_location_diff_reported() -> None:
    a = normalize(_resp(
        status=302,
        headers={"content-type": "text/html", "location": "/mfa"},
    ))
    b = normalize(_resp(
        status=302,
        headers={"content-type": "text/html", "location": "/login"},
    ))
    out = diff(a, b)
    assert any(d.kind == "redirect_location" for d in out)


def test_json_error_code_diff_reported() -> None:
    a = normalize(_resp(
        text='{"error_code": "USER_NOT_FOUND"}',
        content_type="application/json",
    ))
    b = normalize(_resp(
        text='{"error_code": "BAD_PASSWORD"}',
        content_type="application/json",
    ))
    out = diff(a, b)
    assert any(d.kind == "json_error_code" for d in out)


def test_title_diff_reported() -> None:
    a = normalize(_resp(text="<html><head><title>Sign in</title></head></html>"))
    b = normalize(_resp(text="<html><head><title>MFA</title></head></html>"))
    out = diff(a, b)
    assert any(d.kind == "title_text" for d in out)


def test_body_fingerprint_diff_reported_when_unique() -> None:
    """When nothing more semantic than body bytes differs, the diff
    surfaces a `body_text` differentiator — a weak signal per spec
    2.1 §5."""
    a = normalize(_resp(text="<html><body>user not found</body></html>"))
    b = normalize(_resp(text="<html><body>incorrect password</body></html>"))
    out = diff(a, b)
    assert any(d.kind == "body_text" for d in out)


def test_differentiator_carries_redacted_values() -> None:
    """Differentiator values are never raw token / cookie strings —
    the diff layer pre-redacts."""
    a = normalize(_resp(status=200))
    b = normalize(_resp(status=403))
    out = diff(a, b)
    d = next(x for x in out if x.kind == "status_code")
    assert d.invalid_value_redacted == "200"
    assert d.valid_value_redacted == "403"


# ----- classify_abort -----------------------------------------------

@pytest.mark.parametrize(("body", "signal"), [
    ("Please complete the CAPTCHA", AbortSignal.CAPTCHA),
    ("Cloudflare 1020 Access Denied", AbortSignal.WAF),
    ("Your account is locked. Try again in 15 minutes.", AbortSignal.LOCKOUT),
    ("Rate limit exceeded — try again later.", AbortSignal.RATE_LIMIT),
    ("Enter the 6-digit code from your authenticator", AbortSignal.MFA),
])
def test_classify_abort_detects_signals(body: str, signal: AbortSignal) -> None:
    out = normalize(_resp(text=f"<html><body>{body}</body></html>"))
    assert out.abort_signal == signal


def test_classify_abort_none_when_clean() -> None:
    out = normalize(_resp(text="<html><body>welcome</body></html>"))
    assert out.abort_signal is None


def test_classify_abort_standalone_helper_matches() -> None:
    """`classify_abort()` can be called on a NormalizedResponse directly
    without re-parsing. Mirrors the normalize() result."""
    out = normalize(_resp(text="<html><body>CAPTCHA required</body></html>"))
    assert classify_abort(out) == AbortSignal.CAPTCHA


# ----- defensive parsing --------------------------------------------

def test_unparseable_json_does_not_crash() -> None:
    out = normalize(_resp(text="not json{", content_type="application/json"))
    assert out.json_error_code is None
    assert out.json_error_fields == {}


def test_empty_body() -> None:
    out = normalize(_resp(text=""))
    assert out.body_fingerprint != ""  # still hashed, just of empty string
    assert out.title is None
