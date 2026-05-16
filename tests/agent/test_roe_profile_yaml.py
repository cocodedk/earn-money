# tests/agent/test_roe_profile_yaml.py
"""Tests for RoE profile YAML loading."""

import tempfile
from pathlib import Path

import pytest

from earn_money.agent.roe_profile import (
    RoeProfile,
    RoeProfileError,
    RoeSourceType,
)


class TestRoeProfileYaml:
    """Test YAML loading."""

    def test_custom_yaml_profile_loads(self):
        """Custom YAML profile should load correctly."""
        yaml_content = """
name: custom-test
allowed_hosts:
  - target.example.com
  - api.target.example.com
denied_hosts:
  - admin.target.example.com
max_requests: 50
max_posts: 10
max_turns: 20
max_runtime_seconds: 120
max_response_bytes: 8000
delay_between_requests_ms: 1000
allow_get: true
allow_post: true
allow_idor_checks: true
allow_graphql_introspection: true
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_path = Path(f.name)

        try:
            profile = RoeProfile.from_yaml(temp_path, RoeSourceType.CLIENT_CONTRACT, "acme-corp")
            assert profile.name == "custom-test"
            assert profile.allowed_hosts == ["target.example.com", "api.target.example.com"]
            assert "admin.target.example.com" in profile.denied_hosts
            assert profile.max_requests == 50
            assert profile.allow_idor_checks is True
            assert profile.source_type == RoeSourceType.CLIENT_CONTRACT
        finally:
            temp_path.unlink()

    def test_missing_yaml_file_fails(self):
        """Loading missing YAML file should fail."""
        with pytest.raises(RoeProfileError) as exc:
            RoeProfile.from_yaml(Path("/nonexistent.yaml"), RoeSourceType.MANUAL)
        assert "not found" in str(exc.value)

    def test_invalid_yaml_fails(self):
        """Invalid YAML content should fail."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("this: is: not: valid: yaml: [")
            temp_path = Path(f.name)

        try:
            with pytest.raises(RoeProfileError) as exc:
                RoeProfile.from_yaml(temp_path, RoeSourceType.MANUAL)
            assert "YAML" in str(exc.value) or "load" in str(exc.value)
        finally:
            temp_path.unlink()
