# tests/agent/test_roe_profile.py
"""Tests for RoE profile model."""

import tempfile
from pathlib import Path

import pytest
import yaml

from earn_money.agent.roe_profile import (
    RoeProfile,
    RoeProfileError,
    RoeSourceType,
    load_roe_profile,
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
            source_ref="hackerone/example-program"
        )
        
        assert profile.source_type == RoeSourceType.HACKERONE
        assert profile.source_ref == "hackerone/example-program"


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
            assert profile.denied_hosts == ["admin.target.example.com"]
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