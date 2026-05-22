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


def test_oauth_in_body_detected_even_without_oauth_url():
    resp = _resp(200, url="https://example.com/settings",
                 body='<a href="/auth?client_id=abc&redirect_uri=...&response_type=code">Login</a>')
    result = classify_passive_oauth_evidence(resp)
    assert result.detected is True
