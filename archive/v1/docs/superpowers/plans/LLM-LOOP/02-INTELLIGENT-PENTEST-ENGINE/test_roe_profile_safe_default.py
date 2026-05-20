# tests/agent/test_roe_profile_safe_default.py
"""Tests for RoE profile safe default."""

from earn_money.agent.roe_profile import RoeProfile


class TestSafeDefault:
    """Test safe default profile."""

    def test_safe_default_loads(self):
        """Safe default should be loadable and actually safe."""
        profile = RoeProfile.safe_default()

        assert profile.name == "safe-default"
        assert profile.allow_get is True
        assert profile.allow_post is False
        assert profile.allow_bruteforce is False
        assert profile.allow_exploit_chains is False
        assert profile.allow_destructive_actions is False
        assert profile.allow_sensitive_data_capture is False
        assert profile.require_replay_steps is True

    def test_safe_default_allowed_hosts_empty(self):
        """Safe default has empty allowed_hosts, meaning no hosts allowed."""
        profile = RoeProfile.safe_default()
        assert profile.allowed_hosts == []
        assert profile.is_host_allowed("anything.com") is False
