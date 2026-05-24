"""Tests for stub 3.4 broad-domain-scope classification."""
from __future__ import annotations

from apps.stubs._shared.session.cookie_parser import parse_set_cookie
from apps.stubs.broad_domain_scope.classify import (
    DomainResult,
    DomainStatus,
    ScopeIssue,
    classify_cookie,
)


def _c(header: str):
    return parse_set_cookie(header)


def test_parent_domain_confirmed():
    r = classify_cookie(_c("sid=x; Domain=example.test; Path=/; Secure; HttpOnly"), host="app.example.test")
    assert r.status == DomainStatus.CONFIRMED
    assert r.confidence == "high"
    assert r.scope_issue == ScopeIssue.PARENT_DOMAIN


def test_parent_domain_leading_dot_stripped():
    r = classify_cookie(_c("sid=x; Domain=.example.test; Path=/; Secure; HttpOnly"), host="app.example.test")
    assert r.status == DomainStatus.CONFIRMED
    assert r.confidence == "high"
    assert r.scope_issue == ScopeIssue.PARENT_DOMAIN


def test_deep_parent_domain_confirmed():
    r = classify_cookie(_c("sid=x; Domain=example.test; Path=/; Secure; HttpOnly"), host="admin.eu.example.test")
    assert r.status == DomainStatus.CONFIRMED
    assert r.scope_issue == ScopeIssue.PARENT_DOMAIN


def test_host_only_rejected():
    r = classify_cookie(_c("sid=x; Path=/; Secure; HttpOnly"), host="app.example.test")
    assert r.status == DomainStatus.REJECTED
    assert r.confidence == "high"


def test_exact_host_domain_attribute_candidate():
    r = classify_cookie(_c("sid=x; Domain=app.example.test; Path=/; Secure; HttpOnly"), host="app.example.test")
    assert r.status == DomainStatus.CANDIDATE
    assert r.confidence == "low"
    assert r.scope_issue == ScopeIssue.EXACT_HOST_DOMAIN_ATTRIBUTE


def test_apex_domain_attribute_candidate():
    r = classify_cookie(_c("sid=x; Domain=example.test; Path=/; Secure; HttpOnly"), host="example.test")
    assert r.status == DomainStatus.CANDIDATE
    assert r.confidence == "medium"
    assert r.scope_issue == ScopeIssue.APEX_DOMAIN


def test_public_suffix_invalid_rejected():
    r = classify_cookie(_c("sid=x; Domain=test; Path=/; Secure; HttpOnly"), host="app.example.test")
    assert r.status == DomainStatus.REJECTED
    assert r.scope_issue == ScopeIssue.PUBLIC_SUFFIX_INVALID


def test_preference_cookie_not_applicable():
    r = classify_cookie(_c("theme=dark; Domain=example.test; Path=/"), host="app.example.test")
    assert r.status == DomainStatus.NOT_APPLICABLE


def test_csrf_cookie_not_applicable():
    r = classify_cookie(_c("csrf_token=t; Domain=example.test; Path=/"), host="app.example.test")
    assert r.status == DomainStatus.NOT_APPLICABLE


def test_sso_allowlisted_not_applicable():
    r = classify_cookie(
        _c("sso_state=val; Domain=example.test; Path=/; Secure; HttpOnly"),
        host="app.example.test",
        sso_allowlisted=True,
    )
    assert r.status == DomainStatus.NOT_APPLICABLE


def test_result_carries_cookie_name():
    r = classify_cookie(_c("sid=x; Domain=example.test; Path=/"), host="app.example.test")
    assert r.cookie_name == "sid"


def test_unrelated_domain_rejected():
    r = classify_cookie(_c("sid=x; Domain=other.test; Path=/; Secure; HttpOnly"), host="app.example.test")
    assert r.status == DomainStatus.REJECTED


def test_raw_value_not_in_result():
    r = classify_cookie(_c("sid=supersecret; Domain=example.test; Path=/"), host="app.example.test")
    assert "supersecret" not in str(r)
