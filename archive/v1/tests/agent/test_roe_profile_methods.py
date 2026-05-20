# tests/agent/test_roe_profile_methods.py
"""Tests for RoE profile helper methods."""

from earn_money.agent.roe_profile import RoeProfile, RoeSourceType


class TestRoeProfileMethods:
    """Test RoE profile helper methods."""

    def test_is_host_allowed_exact_match(self):
        """Exact host match should be allowed."""
        profile = RoeProfile(
            name="test",
            source_type=RoeSourceType.MANUAL,
            allowed_hosts=["example.com", "api.example.com"],
        )
        assert profile.is_host_allowed("example.com") is True
        assert profile.is_host_allowed("evil.com") is False

    def test_is_host_allowed_wildcard(self):
        """Wildcard patterns should match subdomains."""
        profile = RoeProfile(
            name="test",
            source_type=RoeSourceType.MANUAL,
            allowed_hosts=["*.example.com"],
        )
        assert profile.is_host_allowed("api.example.com") is True
        assert profile.is_host_allowed("sub.api.example.com") is True
        assert profile.is_host_allowed("example.com") is False  # No dot before suffix
        assert profile.is_host_allowed("evil.com") is False

    def test_is_host_denied(self):
        """Denied hosts should be rejected."""
        profile = RoeProfile(
            name="test",
            source_type=RoeSourceType.MANUAL,
            allowed_hosts=["example.com"],
            denied_hosts=["admin.example.com", "*.internal"],
        )
        assert profile.is_host_denied("admin.example.com") is True
        assert profile.is_host_denied("vault.internal") is True
        assert profile.is_host_denied("example.com") is False

    def test_allowed_method(self):
        """HTTP method allowance should match flags."""
        profile = RoeProfile(
            name="test",
            source_type=RoeSourceType.MANUAL,
            allowed_hosts=["example.com"],
            allow_get=True,
            allow_post=True,
            allow_put=False,
        )
        assert profile.allowed_method("GET") is True
        assert profile.allowed_method("POST") is True
        assert profile.allowed_method("PUT") is False
        assert profile.allowed_method("DELETE") is False
        assert profile.allowed_method("OPTIONS") is False  # Unknown method

    def test_to_prompt_summary(self):
        """Prompt summary should include key information."""
        profile = RoeProfile(
            name="test-profile",
            source_type=RoeSourceType.HACKERONE,
            allowed_hosts=["example.com"],
            allow_get=True,
            allow_post=False,
            allow_idor_checks=True,
            allow_bruteforce=False,
        )
        summary = profile.to_prompt_summary()

        assert "RoE Profile: test-profile" in summary
        assert "Source: hackerone" in summary
        assert "Allowed hosts:" in summary
        assert "example.com" in summary
        assert "GET" in summary
        assert "POST" not in summary  # Should not be listed
        assert "IDOR checks: ALLOWED" in summary
        assert "Brute force: DENIED" in summary
