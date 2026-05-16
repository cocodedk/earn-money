# tests/agent/test_roe_profile_model.py
"""Tests for RoE profile Pydantic model validation."""

import pytest

from earn_money.agent.roe_profile import (
    RoeProfile,
    RoeProfileError,
    RoeSourceType,
)


class TestRoeProfileModel:
    """Test Pydantic validation."""

    def test_valid_minimal_profile(self):
        """Minimal valid profile should pass validation."""
        data = {
            "name": "test-profile",
            "allowed_hosts": ["example.com"],
            "max_requests": 100,
            "max_posts": 20,
            "max_turns": 25,
            "max_runtime_seconds": 180,
            "max_response_bytes": 12000,
            "delay_between_requests_ms": 500,
        }
        profile = RoeProfile.from_dict(data, RoeSourceType.MANUAL)
        assert profile.name == "test-profile"
        assert profile.allowed_hosts == ["example.com"]

    def test_missing_allowed_hosts_fails(self):
        """Profile without allowed_hosts should fail."""
        data = {
            "name": "test-profile",
            "max_requests": 100,
        }
        with pytest.raises(RoeProfileError) as exc:
            RoeProfile.from_dict(data, RoeSourceType.MANUAL)
        assert "allowed_hosts" in str(exc.value)

    def test_negative_max_requests_fails(self):
        """Negative max_requests should fail."""
        data = {
            "name": "test-profile",
            "allowed_hosts": ["example.com"],
            "max_requests": -1,
            "max_posts": 20,
            "max_turns": 25,
            "max_runtime_seconds": 180,
            "max_response_bytes": 12000,
            "delay_between_requests_ms": 500,
        }
        with pytest.raises(RoeProfileError) as exc:
            RoeProfile.from_dict(data, RoeSourceType.MANUAL)
        assert "max_requests" in str(exc.value)

    def test_max_posts_exceeds_max_requests_fails(self):
        """max_posts cannot exceed max_requests."""
        data = {
            "name": "test-profile",
            "allowed_hosts": ["example.com"],
            "max_requests": 10,
            "max_posts": 20,  # Exceeds max_requests
            "max_turns": 25,
            "max_runtime_seconds": 180,
            "max_response_bytes": 12000,
            "delay_between_requests_ms": 500,
        }
        with pytest.raises(RoeProfileError) as exc:
            RoeProfile.from_dict(data, RoeSourceType.MANUAL)
        assert "max_posts" in str(exc.value)

    def test_unknown_field_fails(self):
        """Extra fields should be rejected."""
        data = {
            "name": "test-profile",
            "allowed_hosts": ["example.com"],
            "max_requests": 100,
            "max_posts": 20,
            "max_turns": 25,
            "max_runtime_seconds": 180,
            "max_response_bytes": 12000,
            "delay_between_requests_ms": 500,
            "unknown_field": "should fail",
        }
        with pytest.raises(RoeProfileError) as exc:
            RoeProfile.from_dict(data, RoeSourceType.MANUAL)
        assert "unknown_field" in str(exc.value)

    def test_permissions_default_to_safe(self):
        """Test permissions should default to False (safe)."""
        data = {
            "name": "test-profile",
            "allowed_hosts": ["example.com"],
            "max_requests": 100,
            "max_posts": 20,
            "max_turns": 25,
            "max_runtime_seconds": 180,
            "max_response_bytes": 12000,
            "delay_between_requests_ms": 500,
        }
        profile = RoeProfile.from_dict(data, RoeSourceType.MANUAL)

        # All dangerous permissions should be False by default
        assert profile.allow_bruteforce is False
        assert profile.allow_exploit_chains is False
        assert profile.allow_destructive_actions is False
        assert profile.allow_rate_limit_testing is False
        assert profile.allow_sensitive_data_capture is False

    def test_denied_hosts_gets_defaults(self):
        """denied_hosts should include dangerous defaults."""
        data = {
            "name": "test-profile",
            "allowed_hosts": ["example.com"],
            "max_requests": 100,
            "max_posts": 20,
            "max_turns": 25,
            "max_runtime_seconds": 180,
            "max_response_bytes": 12000,
            "delay_between_requests_ms": 500,
            "denied_hosts": ["evil.com"],
        }
        profile = RoeProfile.from_dict(data, RoeSourceType.MANUAL)

        # Should include both explicit and defaults
        assert "evil.com" in profile.denied_hosts
        assert "localhost" in profile.denied_hosts
        assert "127.0.0.1" in profile.denied_hosts
        assert "169.254.169.254" in profile.denied_hosts

    def test_source_metadata_is_stored(self):
        """Source type and reference should be stored."""
        data = {
            "name": "test-profile",
            "allowed_hosts": ["example.com"],
            "max_requests": 100,
            "max_posts": 20,
            "max_turns": 25,
            "max_runtime_seconds": 180,
            "max_response_bytes": 12000,
            "delay_between_requests_ms": 500,
        }
        profile = RoeProfile.from_dict(
            data,
            RoeSourceType.HACKERONE,
            source_ref="hackerone/example-program",
        )
        assert profile.source_type == RoeSourceType.HACKERONE
        assert profile.source_ref == "hackerone/example-program"
