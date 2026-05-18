"""Tests for ScopePolicy."""

import pytest

from earn_money.agent.roe_profile import RoeProfile, RoeSourceType
from earn_money.agent.scope_policy import ScopeDenied, ScopePolicy


def _policy(allowed: list[str], denied: list[str] | None = None) -> ScopePolicy:
    profile = RoeProfile(
        name="test",
        source_type=RoeSourceType.MANUAL,
        allowed_hosts=allowed,
        denied_hosts=denied or [],
        max_requests=100,
        max_posts=20,
        max_turns=25,
        max_runtime_seconds=180,
        max_response_bytes=12000,
        delay_between_requests_ms=0,
    )
    return ScopePolicy(profile, "https://target.example.com")


class TestScopePolicy:
    def test_relative_path_resolves_under_base_url(self):
        sp = _policy(["target.example.com"])
        result = sp.check("/api/users")
        assert result == "https://target.example.com/api/users"

    def test_same_host_absolute_url_allowed(self):
        sp = _policy(["target.example.com"])
        result = sp.check("https://target.example.com/foo")
        assert "target.example.com" in result

    def test_allowed_wildcard_host_allowed(self):
        sp = _policy(["*.example.com"])
        result = sp.check("https://api.example.com/endpoint")
        assert "api.example.com" in result

    def test_denied_wildcard_host_rejected(self):
        sp = _policy(["*.example.com"], denied=["admin.example.com"])
        with pytest.raises(ScopeDenied):
            sp.check("https://admin.example.com/secret")

    def test_external_host_rejected(self):
        sp = _policy(["target.example.com"])
        with pytest.raises(ScopeDenied):
            sp.check("https://evil.com/steal")

    def test_unsupported_scheme_rejected(self):
        sp = _policy(["target.example.com"])
        with pytest.raises(ScopeDenied):
            sp.check("ftp://target.example.com/file")

    def test_path_traversal_rejected(self):
        sp = _policy(["target.example.com"])
        with pytest.raises(ScopeDenied):
            sp.check("https://target.example.com/../etc/passwd")

    def test_localhost_rejected_by_default(self):
        sp = _policy(["target.example.com"])
        with pytest.raises(ScopeDenied):
            sp.check("http://localhost/admin")

    def test_127_0_0_1_rejected_by_default(self):
        sp = _policy(["target.example.com"])
        with pytest.raises(ScopeDenied):
            sp.check("http://127.0.0.1/secret")

    def test_169_254_169_254_rejected_by_default(self):
        sp = _policy(["target.example.com"])
        with pytest.raises(ScopeDenied):
            sp.check("http://169.254.169.254/latest/meta-data/")

    def test_same_host_redirect_allowed(self):
        sp = _policy(["target.example.com"])
        result = sp.check_redirect("/dashboard", "https://target.example.com/login")
        assert "target.example.com" in result

    def test_external_redirect_rejected(self):
        sp = _policy(["target.example.com"])
        with pytest.raises(ScopeDenied):
            sp.check_redirect("https://attacker.com/steal", "https://target.example.com/login")
