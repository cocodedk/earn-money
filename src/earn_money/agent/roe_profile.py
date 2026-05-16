from __future__ import annotations

import fnmatch
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

_ALWAYS_DENIED = ["localhost", "127.0.0.1", "169.254.169.254"]


class RoeProfileError(Exception):
    pass


class RoeSourceType(StrEnum):
    CLIENT_CONTRACT = "client_contract"
    HACKERONE = "hackerone"
    BUG_BOUNTY = "bug_bounty"
    INTERNAL_LAB = "internal_lab"
    MANUAL = "manual"


class RoeProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    source_type: RoeSourceType = RoeSourceType.MANUAL
    source_ref: str | None = None

    allowed_hosts: list[str]
    denied_hosts: list[str] = []

    max_requests: int = 100
    max_posts: int = 20
    max_turns: int = 25
    max_runtime_seconds: int = 180
    max_response_bytes: int = 12000
    delay_between_requests_ms: int = 500

    allow_get: bool = True
    allow_post: bool = False
    allow_put: bool = False
    allow_patch: bool = False
    allow_delete: bool = False

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

    require_replay_steps: bool = True
    require_non_destructive_poc: bool = True
    allow_sensitive_data_capture: bool = False
    max_evidence_body_bytes: int = 1000

    @field_validator("max_requests")
    @classmethod
    def max_requests_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("max_requests must be non-negative")
        return v

    @model_validator(mode="after")
    def check_posts_and_merge_denied(self) -> RoeProfile:
        if self.max_posts > self.max_requests:
            raise ValueError(
                f"max_posts ({self.max_posts}) cannot exceed max_requests ({self.max_requests})"
            )
        for h in _ALWAYS_DENIED:
            if h not in self.denied_hosts:
                self.denied_hosts.append(h)
        return self

    # ── host/method helpers ──────────────────────────────────────────────────

    def is_host_allowed(self, host: str) -> bool:
        return any(fnmatch.fnmatch(host, p) for p in self.allowed_hosts)

    def is_host_denied(self, host: str) -> bool:
        return any(fnmatch.fnmatch(host, p) for p in self.denied_hosts)

    def allowed_method(self, method: str) -> bool:
        return {
            "GET": self.allow_get,
            "POST": self.allow_post,
            "PUT": self.allow_put,
            "PATCH": self.allow_patch,
            "DELETE": self.allow_delete,
        }.get(method.upper(), False)

    def to_prompt_summary(self) -> str:
        methods = [m for m in ("GET", "POST", "PUT", "PATCH", "DELETE") if self.allowed_method(m)]
        hosts = "\n".join(f"  {h}" for h in self.allowed_hosts)
        return (
            f"RoE Profile: {self.name}\n"
            f"Source: {self.source_type.value}\n"
            f"Allowed hosts:\n{hosts}\n"
            f"Allowed methods: {', '.join(methods) or 'none'}\n"
            f"IDOR checks: {'ALLOWED' if self.allow_idor_checks else 'DENIED'}\n"
            f"Brute force: {'ALLOWED' if self.allow_bruteforce else 'DENIED'}\n"
            f"Exploit chains: {'ALLOWED' if self.allow_exploit_chains else 'DENIED'}\n"
            f"Destructive actions: {'ALLOWED' if self.allow_destructive_actions else 'DENIED'}"
        )

    # ── constructors ─────────────────────────────────────────────────────────

    @classmethod
    def safe_default(cls) -> RoeProfile:
        return cls(name="safe-default", source_type=RoeSourceType.MANUAL, allowed_hosts=[])

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        source_type: RoeSourceType,
        source_ref: str | None = None,
    ) -> RoeProfile:
        try:
            return cls(source_type=source_type, source_ref=source_ref, **data)
        except Exception as e:
            raise RoeProfileError(str(e)) from e

    @classmethod
    def from_yaml(
        cls,
        path: Path,
        source_type: RoeSourceType,
        source_ref: str | None = None,
    ) -> RoeProfile:
        if not path.exists():
            raise RoeProfileError(f"Profile not found: {path}")
        try:
            raw = yaml.safe_load(path.read_text())
        except yaml.YAMLError as e:
            raise RoeProfileError(f"YAML load error: {e}") from e
        if not isinstance(raw, dict):
            raise RoeProfileError("Profile must be a YAML mapping")
        return cls.from_dict(_flatten(raw), source_type, source_ref)


def _flatten(data: dict[str, Any]) -> dict[str, Any]:
    """Flatten nested scope/traffic/methods/testing/evidence sections if present."""
    result: dict[str, Any] = {}
    for key, value in data.items():
        _NESTED = ("scope", "traffic", "methods", "testing", "evidence")
        if key in _NESTED and isinstance(value, dict):
            result.update(value)
        else:
            result[key] = value
    return result


def load_roe_profile(
    path: Path | None = None,
    source_type: RoeSourceType | None = None,
    source_ref: str | None = None,
) -> RoeProfile:
    if path is None:
        return RoeProfile.safe_default()
    return RoeProfile.from_yaml(path, source_type or RoeSourceType.MANUAL, source_ref)
