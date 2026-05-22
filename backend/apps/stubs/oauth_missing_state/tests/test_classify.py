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
