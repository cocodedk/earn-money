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


def test_3xx_no_location_header_is_inconclusive():
    resp = _resp(302)  # no Location header
    result = classify_redirect_response(resp, SCANNER)
    assert result.status != "confirmed"
    assert result.validation_result != ValidationResult.ACCEPTED_UNTRUSTED_REDIRECT


def test_3xx_to_non_scanner_origin_is_inconclusive():
    resp = _resp(302, "https://app.example.test/oauth/callback?code=abc")
    result = classify_redirect_response(resp, SCANNER)
    assert result.status != "confirmed"
    assert result.validation_result != ValidationResult.ACCEPTED_UNTRUSTED_REDIRECT


def test_4xx_with_non_json_body_no_phrase_is_inconclusive():
    resp = _resp(400, body="Bad request")
    result = classify_redirect_response(resp, SCANNER)
    assert result.status == "rejected"
    assert result.validation_result == ValidationResult.INCONCLUSIVE


def test_4xx_with_non_json_body_containing_reject_phrase():
    resp = _resp(400, body="Error: invalid_redirect_uri for this client")
    result = classify_redirect_response(resp, SCANNER)
    assert result.status == "rejected"
    assert result.validation_result == ValidationResult.REJECTED_INVALID_REDIRECT
