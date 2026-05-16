# src/earn_money/agent/roe_profile.py
"""Rules of Engagement profile for authorized security testing.

The RoE profile defines legal boundaries for the LLM probe loop.
It must be loaded from YAML and validated before use.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator


# ============================================================================
# Exception
# ============================================================================

class RoeProfileError(Exception):
    """Raised when RoE profile is invalid or missing required fields."""
    pass


# ============================================================================
# Source types
# ============================================================================

class RoeSourceType(str, Enum):
    CLIENT_CONTRACT = "client_contract"
    HACKERONE = "hackerone"
    BUG_BOUNTY = "bug_bounty"
    INTERNAL_LAB = "internal_lab"
    MANUAL = "manual"


# ============================================================================
# Pydantic model for validation
# ============================================================================

class RoeProfileModel(BaseModel):
    """Pydantic model for RoE profile validation."""
    
    # Identity
    name: str = Field(min_length=1)
    
    # Scope
    allowed_hosts: list[str] = Field(min_length=1)
    denied_hosts: list[str] = Field(default_factory=list)
    
    # Traffic limits
    max_requests: int = Field(ge=1, le=10000)
    max_posts: int = Field(ge=0, le=5000)
    max_turns: int = Field(ge=1, le=500)
    max_runtime_seconds: int = Field(ge=1, le=3600)
    max_response_bytes: int = Field(ge=1024, le=1024*1024)  # 1KB to 1MB
    delay_between_requests_ms: int = Field(ge=0, le=60000)
    
    # HTTP methods
    allow_get: bool = True
    allow_post: bool = False
    allow_put: bool = False
    allow_patch: bool = False
    allow_delete: bool = False
    
    # Test permissions
    allow_authenticated_testing: bool = False
    allow_rate_limit_testing: bool = False
    allow_bruteforce: bool = False
    allow_password_spraying: bool = False
    allow_credential_stuffing: bool = False
    allow_exploit_chains: bool = False
    allow_destructive_actions: bool = False
    allow_file_upload_tests: bool = False
    allow_graphql_introspection: bool = False
    allow_openapi_probing: bool = False
    allow_idor_checks: bool = False
    allow_xss_probe_payloads: bool = False
    allow_sqli_probe_payloads: bool = False
    
    # Evidence rules
    require_replay_steps: bool = True
    require_non_destructive_poc: bool = True
    allow_sensitive_data_capture: bool = False
    max_evidence_body_bytes: int = Field(ge=256, le=102400, default=1000)
    
    @field_validator("denied_hosts")
    @classmethod
    def validate_denied_hosts(cls, v: list[str]) -> list[str]:
        """Ensure denied_hosts has sensible defaults for common dangerous targets."""
        defaults = ["localhost", "127.0.0.1", "::1", "169.254.169.254", "metadata.google.internal"]
        merged = list(set(defaults + v))
        return merged
    
    @field_validator("max_posts")
    @classmethod
    def validate_max_posts_vs_requests(cls, v: int, info) -> int:
        """Ensure max_posts doesn't exceed max_requests."""
        data = info.data
        if "max_requests" in data and v > data["max_requests"]:
            raise ValueError(f"max_posts ({v}) cannot exceed max_requests ({data['max_requests']})")
        return v
    
    @field_validator("max_response_bytes", "max_evidence_body_bytes")
    @classmethod
    def validate_body_size_relationship(cls, v: int, info) -> int:
        """Ensure evidence bytes don't exceed response bytes."""
        data = info.data
        field_name = info.field_name
        
        if field_name == "max_evidence_body_bytes" and "max_response_bytes" in data:
            if v > data["max_response_bytes"]:
                raise ValueError(f"max_evidence_body_bytes ({v}) cannot exceed max_response_bytes ({data['max_response_bytes']})")
        
        return v
    
    class Config:
        extra = "forbid"  # Reject unknown fields


# ============================================================================
# RoeProfile dataclass (runtime representation)
# ============================================================================

@dataclass
class RoeProfile:
    """Rules of Engagement profile for LLM probe loop."""
    
    # Identity
    name: str
    
    # Source metadata
    source_type: RoeSourceType
    source_ref: Optional[str] = None
    
    # Scope
    allowed_hosts: list[str] = field(default_factory=list)
    denied_hosts: list[str] = field(default_factory=list)
    
    # Traffic limits
    max_requests: int = 100
    max_posts: int = 20
    max_turns: int = 25
    max_runtime_seconds: int = 180
    max_response_bytes: int = 12000
    delay_between_requests_ms: int = 500
    
    # HTTP methods
    allow_get: bool = True
    allow_post: bool = False
    allow_put: bool = False
    allow_patch: bool = False
    allow_delete: bool = False
    
    # Test permissions
    allow_authenticated_testing: bool = False
    allow_rate_limit_testing: bool = False
    allow_bruteforce: bool = False
    allow_password_spraying: bool = False
    allow_credential_stuffing: bool = False
    allow_exploit_chains: bool = False
    allow_destructive_actions: bool = False
    allow_file_upload_tests: bool = False
    allow_graphql_introspection: bool = False
    allow_openapi_probing: bool = False
    allow_idor_checks: bool = False
    allow_xss_probe_payloads: bool = False
    allow_sqli_probe_payloads: bool = False
    
    # Evidence rules
    require_replay_steps: bool = True
    require_non_destructive_poc: bool = True
    allow_sensitive_data_capture: bool = False
    max_evidence_body_bytes: int = 1000
    
    @classmethod
    def from_dict(cls, data: dict, source_type: RoeSourceType, source_ref: Optional[str] = None) -> "RoeProfile":
        """Create RoE profile from validated dictionary."""
        # Validate with Pydantic first
        try:
            validated = RoeProfileModel(**data)
        except ValidationError as e:
            raise RoeProfileError(f"Invalid RoE profile: {e}")
        
        # Convert to dataclass
        return cls(
            name=validated.name,
            source_type=source_type,
            source_ref=source_ref,
            allowed_hosts=validated.allowed_hosts,
            denied_hosts=validated.denied_hosts,
            max_requests=validated.max_requests,
            max_posts=validated.max_posts,
            max_turns=validated.max_turns,
            max_runtime_seconds=validated.max_runtime_seconds,
            max_response_bytes=validated.max_response_bytes,
            delay_between_requests_ms=validated.delay_between_requests_ms,
            allow_get=validated.allow_get,
            allow_post=validated.allow_post,
            allow_put=validated.allow_put,
            allow_patch=validated.allow_patch,
            allow_delete=validated.allow_delete,
            allow_authenticated_testing=validated.allow_authenticated_testing,
            allow_rate_limit_testing=validated.allow_rate_limit_testing,
            allow_bruteforce=validated.allow_bruteforce,
            allow_password_spraying=validated.allow_password_spraying,
            allow_credential_stuffing=validated.allow_credential_stuffing,
            allow_exploit_chains=validated.allow_exploit_chains,
            allow_destructive_actions=validated.allow_destructive_actions,
            allow_file_upload_tests=validated.allow_file_upload_tests,
            allow_graphql_introspection=validated.allow_graphql_introspection,
            allow_openapi_probing=validated.allow_openapi_probing,
            allow_idor_checks=validated.allow_idor_checks,
            allow_xss_probe_payloads=validated.allow_xss_probe_payloads,
            allow_sqli_probe_payloads=validated.allow_sqli_probe_payloads,
            require_replay_steps=validated.require_replay_steps,
            require_non_destructive_poc=validated.require_non_destructive_poc,
            allow_sensitive_data_capture=validated.allow_sensitive_data_capture,
            max_evidence_body_bytes=validated.max_evidence_body_bytes,
        )
    
    @classmethod
    def from_yaml(cls, path: Path, source_type: RoeSourceType, source_ref: Optional[str] = None) -> "RoeProfile":
        """Load RoE profile from YAML file."""
        if not path.exists():
            raise RoeProfileError(f"RoE profile not found: {path}")
        
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        
        if not isinstance(data, dict):
            raise RoeProfileError(f"Invalid YAML: expected dict, got {type(data)}")
        
        return cls.from_dict(data, source_type, source_ref)
    
    @classmethod
    def safe_default(cls) -> "RoeProfile":
        """Return the safest possible RoE profile for initial testing.
        
        This profile:
        - Requires explicit host allowlist
        - Denies all dangerous methods
        - Denies all aggressive test categories
        - Requires replay steps for evidence
        - Disables sensitive data capture
        """
        return cls(
            name="safe-default",
            source_type=RoeSourceType.MANUAL,
            source_ref="builtin-safe-default",
            allowed_hosts=[],  # Empty means NO hosts allowed - must be overridden
            denied_hosts=[],   # Will get defaults from validator
            max_requests=50,
            max_posts=5,
            max_turns=15,
            max_runtime_seconds=120,
            max_response_bytes=8000,
            delay_between_requests_ms=1000,
            allow_get=True,
            allow_post=False,
            allow_put=False,
            allow_patch=False,
            allow_delete=False,
            allow_authenticated_testing=False,
            allow_rate_limit_testing=False,
            allow_bruteforce=False,
            allow_password_spraying=False,
            allow_credential_stuffing=False,
            allow_exploit_chains=False,
            allow_destructive_actions=False,
            allow_file_upload_tests=False,
            allow_graphql_introspection=False,
            allow_openapi_probing=False,
            allow_idor_checks=False,
            allow_xss_probe_payloads=False,
            allow_sqli_probe_payloads=False,
            require_replay_steps=True,
            require_non_destructive_poc=True,
            allow_sensitive_data_capture=False,
            max_evidence_body_bytes=500,
        )
    
    def is_host_allowed(self, host: str) -> bool:
        """Check if a host is in scope."""
        if not self.allowed_hosts:
            return False
        
        # Exact match
        if host in self.allowed_hosts:
            return True
        
        # Wildcard match (*.example.com)
        for pattern in self.allowed_hosts:
            if pattern.startswith("*."):
                suffix = pattern[1:]  # .example.com
                if host.endswith(suffix):
                    return True
        
        return False
    
    def is_host_denied(self, host: str) -> bool:
        """Check if a host is explicitly denied."""
        # Exact match
        if host in self.denied_hosts:
            return True
        
        # Wildcard match
        for pattern in self.denied_hosts:
            if pattern.startswith("*."):
                suffix = pattern[1:]
                if host.endswith(suffix):
                    return True
        
        return False
    
    def allowed_method(self, method: str) -> bool:
        """Check if HTTP method is allowed."""
        method_upper = method.upper()
        return {
            "GET": self.allow_get,
            "POST": self.allow_post,
            "PUT": self.allow_put,
            "PATCH": self.allow_patch,
            "DELETE": self.allow_delete,
        }.get(method_upper, False)
    
    def to_prompt_summary(self) -> str:
        """Return a human-readable summary for the LLM prompt."""
        lines = [
            f"RoE Profile: {self.name}",
            f"Source: {self.source_type.value}",
            "",
            "Allowed hosts:",
        ]
        
        for host in self.allowed_hosts:
            lines.append(f"  - {host}")
        
        lines.extend([
            "",
            "Allowed HTTP methods:",
        ])
        
        for method in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
            if self.allowed_method(method):
                lines.append(f"  - {method}")
        
        lines.extend([
            "",
            "Permissions:",
        ])
        
        perms = [
            ("IDOR checks", self.allow_idor_checks),
            ("GraphQL introspection", self.allow_graphql_introspection),
            ("OpenAPI probing", self.allow_openapi_probing),
            ("Brute force", self.allow_bruteforce),
            ("Rate limit testing", self.allow_rate_limit_testing),
            ("Exploit chains", self.allow_exploit_chains),
            ("Destructive actions", self.allow_destructive_actions),
            ("Sensitive data capture", self.allow_sensitive_data_capture),
        ]
        
        for name, allowed in perms:
            status = "ALLOWED" if allowed else "DENIED"
            lines.append(f"  - {name}: {status}")
        
        lines.extend([
            "",
            "Limits:",
            f"  - Max requests: {self.max_requests}",
            f"  - Max POST: {self.max_posts}",
            f"  - Max turns: {self.max_turns}",
            f"  - Max runtime: {self.max_runtime_seconds}s",
            f"  - Response truncation: {self.max_response_bytes} bytes",
            "",
            "Evidence:",
            f"  - Replay steps required: {self.require_replay_steps}",
            f"  - Non-destructive POC required: {self.require_non_destructive_poc}",
        ])
        
        return "\n".join(lines)


# ============================================================================
# Convenience function
# ============================================================================

def load_roe_profile(
    path: Optional[Path] = None,
    source_type: RoeSourceType = RoeSourceType.MANUAL,
    source_ref: Optional[str] = None,
) -> RoeProfile:
    """Load RoE profile from YAML or return safe default."""
    if path is None:
        return RoeProfile.safe_default()
    
    return RoeProfile.from_yaml(path, source_type, source_ref)