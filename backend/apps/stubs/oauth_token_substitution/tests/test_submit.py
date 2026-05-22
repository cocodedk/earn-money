"""Tests for stub 2.16 two-account substitution submit."""
from __future__ import annotations
from unittest.mock import MagicMock
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
        else:  # pragma: no cover — only /login and /oauth/callback are POSTed
            pass
        return r
    def get(url, **kwargs):
        r = MagicMock()
        r.status_code = 200
        if "/oauth/authorize" in url:
            r.status_code = 302
            r.headers = {"Location": "http://localhost/cb?code=code-abc"}
        elif "/me" in url:  # pragma: no cover — /me not called by run_substitution_test
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


def test_no_code_in_location_returns_candidate():
    http = MagicMock()
    def post(url, **kwargs):
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = {"token": "tok-a", "userId": "user_a"}
        return r
    def get(url, **kwargs):
        r = MagicMock()
        r.status_code = 302
        r.headers = {"Location": "http://localhost/cb"}  # no code= in Location
        return r
    http.post = post
    http.get = get
    result = run_substitution_test(
        base_url="http://localhost:3000",
        cred_a=("user_a", "pass-a"),
        cred_b=("user_b", "pass-b"),
        http=http,
    )
    assert result.status == "candidate"
    assert result.substitution_attempted is False


def test_login_b_failure_returns_candidate():
    call_count = {"n": 0}
    http = MagicMock()
    def post(url, **kwargs):
        r = MagicMock()
        if "/login" in url:
            call_count["n"] += 1
            r.status_code = 200 if call_count["n"] == 1 else 401
            r.json.return_value = {"token": "tok", "userId": "user_a"}
        elif "/oauth/callback" in url:  # pragma: no cover — login_b fails; callback never POSTed
            r.status_code = 200
            r.json.return_value = {"marker": "x"}
        return r
    def get(url, **kwargs):
        r = MagicMock()
        r.status_code = 302
        r.headers = {"Location": "http://localhost/cb?code=code-abc"}
        return r
    http.post = post
    http.get = get
    result = run_substitution_test(
        base_url="http://localhost:3000",
        cred_a=("user_a", "pass-a"),
        cred_b=("user_b", "pass-b"),
        http=http,
    )
    assert result.status == "candidate"
    assert result.substitution_attempted is False
