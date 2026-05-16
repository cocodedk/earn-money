from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from earn_money.agent.roe_profile import RoeProfile

ActionCategory = Literal[
    "recon",
    "http_get",
    "http_post",
    "auth",
    "idor_check",
    "graphql_introspection",
    "openapi_probe",
    "rate_limit_test",
    "bruteforce",
    "xss_probe",
    "sqli_probe",
    "file_upload_test",
    "exploit_chain",
    "destructive",
    "report_candidate",
    "store_memory",
    "stop",
]


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str


_KNOWN_CATEGORIES: frozenset[str] = frozenset(
    [
        "recon", "http_get", "http_post", "auth", "idor_check",
        "graphql_introspection", "openapi_probe", "rate_limit_test",
        "bruteforce", "xss_probe", "sqli_probe", "file_upload_test",
        "exploit_chain", "destructive", "report_candidate", "store_memory", "stop",
    ]
)


class RoePolicy:
    def __init__(self, profile: RoeProfile) -> None:
        self._p = profile

    def decide(self, category: str, method: str | None = None) -> PolicyDecision:
        if category not in _KNOWN_CATEGORIES:
            return PolicyDecision(False, f"Unknown action category: {category!r}")

        p = self._p

        if category == "http_get":
            if not p.allow_get:
                return PolicyDecision(False, "GET not allowed by RoE profile")
            return PolicyDecision(True, "GET allowed")

        if category == "http_post":
            if not p.allow_post:
                return PolicyDecision(False, "POST not allowed by RoE profile")
            return PolicyDecision(True, "POST allowed")

        if category == "auth":
            if not p.allow_authenticated_testing:
                return PolicyDecision(False, "authenticated testing not allowed by RoE profile")
            return PolicyDecision(True, "auth allowed")

        if category == "idor_check":
            if not p.allow_idor_checks:
                return PolicyDecision(False, "IDOR checks not allowed by RoE profile")
            return PolicyDecision(True, "IDOR check allowed")

        if category == "graphql_introspection":
            if not p.allow_graphql_introspection:
                return PolicyDecision(False, "GraphQL introspection not allowed by RoE profile")
            return PolicyDecision(True, "GraphQL introspection allowed")

        if category == "openapi_probe":
            if not p.allow_openapi_probing:
                return PolicyDecision(False, "OpenAPI probing not allowed by RoE profile")
            return PolicyDecision(True, "OpenAPI probing allowed")

        if category == "rate_limit_test":
            if not p.allow_rate_limit_testing:
                return PolicyDecision(False, "rate-limit testing not allowed by RoE profile")
            return PolicyDecision(True, "rate-limit test allowed")

        if category == "bruteforce":
            if not p.allow_bruteforce:
                return PolicyDecision(False, "brute force not allowed by RoE profile")
            return PolicyDecision(True, "brute force allowed")

        if category == "xss_probe":
            if not p.allow_xss_probe_payloads:
                return PolicyDecision(False, "XSS probe payloads not allowed by RoE profile")
            return PolicyDecision(True, "XSS probe allowed")

        if category == "sqli_probe":
            if not p.allow_sqli_probe_payloads:
                return PolicyDecision(False, "SQLi probe payloads not allowed by RoE profile")
            return PolicyDecision(True, "SQLi probe allowed")

        if category == "file_upload_test":
            if not p.allow_file_upload_tests:
                return PolicyDecision(False, "file upload tests not allowed by RoE profile")
            return PolicyDecision(True, "file upload test allowed")

        if category == "exploit_chain":
            if not p.allow_exploit_chains:
                return PolicyDecision(False, "exploit chains not allowed by RoE profile")
            return PolicyDecision(True, "exploit chain allowed")

        if category == "destructive":
            if not p.allow_destructive_actions:
                return PolicyDecision(False, "destructive actions not allowed by RoE profile")
            return PolicyDecision(True, "destructive action allowed")

        # Always-allowed non-network categories
        return PolicyDecision(True, f"{category} allowed")
