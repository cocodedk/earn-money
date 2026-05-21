"""Unit tests for stub 2.17 account-linking flaw classification."""
from __future__ import annotations
from unittest.mock import MagicMock
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


def test_client_controlled_provider_identity_detected():
    resp = _resp(200, method="GET", url="http://example.com/auth/link/callback-client-id",
                 body='{"ok":true,"identity_source":"client_parameter"}')
    result = classify_link_flaw(resp, endpoint_url="http://example.com/auth/link/callback-client-id")
    assert result is not None
    assert result.kind == AccountLinkingFlawKind.CALLBACK_ACCEPTS_CLIENT_IDENTITY


def test_redirect_without_location_not_flagged():
    resp = _resp(302, url="http://example.com/auth/link/start", headers={})
    result = classify_link_flaw(resp, endpoint_url="http://example.com/auth/link/start")
    assert result is None


def test_non_linking_endpoint_not_flagged():
    resp = _resp(200, url="http://example.com/dashboard", body="<html>Welcome</html>")
    result = classify_link_flaw(resp, endpoint_url="http://example.com/dashboard")
    assert result is None
