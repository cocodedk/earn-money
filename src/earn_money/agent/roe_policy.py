from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, get_args

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

_KNOWN_CATEGORIES: frozenset[str] = frozenset(get_args(ActionCategory))


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str


# Gated categories: category → (RoE-profile attr getter, human label).
# Categories not in this table are always allowed once they pass the
# _KNOWN_CATEGORIES guard (recon, report_candidate, store_memory, stop).
_GATED: dict[str, tuple[Callable[[RoeProfile], bool], str]] = {
    "http_get": (lambda p: p.allow_get, "GET"),
    "http_post": (lambda p: p.allow_post, "POST"),
    "auth": (lambda p: p.allow_authenticated_testing, "authenticated testing"),
    "idor_check": (lambda p: p.allow_idor_checks, "IDOR checks"),
    "graphql_introspection": (lambda p: p.allow_graphql_introspection, "GraphQL introspection"),
    "openapi_probe": (lambda p: p.allow_openapi_probing, "OpenAPI probing"),
    "rate_limit_test": (lambda p: p.allow_rate_limit_testing, "rate-limit testing"),
    "bruteforce": (lambda p: p.allow_bruteforce, "brute force"),
    "xss_probe": (lambda p: p.allow_xss_probe_payloads, "XSS probe payloads"),
    "sqli_probe": (lambda p: p.allow_sqli_probe_payloads, "SQLi probe payloads"),
    "file_upload_test": (lambda p: p.allow_file_upload_tests, "file upload tests"),
    "exploit_chain": (lambda p: p.allow_exploit_chains, "exploit chains"),
    "destructive": (lambda p: p.allow_destructive_actions, "destructive actions"),
}


class RoePolicy:
    def __init__(self, profile: RoeProfile) -> None:
        self._p = profile

    def decide(self, category: str, method: str | None = None) -> PolicyDecision:
        if category not in _KNOWN_CATEGORIES:
            return PolicyDecision(False, f"Unknown action category: {category!r}")

        gated = _GATED.get(category)
        if gated is None:
            return PolicyDecision(True, f"{category} allowed")

        allow_fn, label = gated
        if not allow_fn(self._p):
            return PolicyDecision(False, f"{label} not allowed by RoE profile")
        return PolicyDecision(True, f"{label} allowed")
