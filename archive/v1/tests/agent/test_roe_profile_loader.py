# tests/agent/test_roe_profile_loader.py
"""Tests for the load_roe_profile convenience function."""

import tempfile
from pathlib import Path

from earn_money.agent.roe_profile import RoeSourceType, load_roe_profile


class TestLoadRoeProfile:
    """Test convenience loader function."""

    def test_load_without_path_returns_safe_default(self):
        """No path should return safe default."""
        profile = load_roe_profile()
        assert profile.name == "safe-default"

    def test_load_with_path_loads_yaml(self):
        """Path should load YAML."""
        yaml_content = """
name: loaded-test
allowed_hosts: ["example.com"]
max_requests: 100
max_posts: 20
max_turns: 25
max_runtime_seconds: 180
max_response_bytes: 12000
delay_between_requests_ms: 500
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_path = Path(f.name)

        try:
            profile = load_roe_profile(temp_path, RoeSourceType.BUG_BOUNTY, "bugcrowd/test")
            assert profile.name == "loaded-test"
            assert profile.source_type == RoeSourceType.BUG_BOUNTY
        finally:
            temp_path.unlink()
