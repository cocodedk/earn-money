"""Stub 3.4 — Broad Domain Scope classification."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from apps.stubs._shared.session.cookie_parser import ParsedCookie, Sensitivity
from apps.stubs._shared.types import Confidence

# Single-label public suffixes that are invalid as Domain= attributes.
# NOTE: multi-label suffixes (e.g. co.uk, com.au) are not handled here — a full
# Public Suffix List (tldextract) integration is a future improvement. Stubs operate
# on .test/.cocode.dk fixtures where this gap does not produce false results.
_PUBLIC_SUFFIXES: frozenset[str] = frozenset({
    "com", "net", "org", "io", "co", "uk", "de", "fr", "test", "local",
    "example", "invalid", "localhost",
})


class DomainStatus(str, Enum):
    CONFIRMED = "confirmed"
    CANDIDATE = "candidate"
    REJECTED = "rejected"
    NOT_APPLICABLE = "not_applicable"


class ScopeIssue(str, Enum):
    PARENT_DOMAIN = "parent_domain"
    APEX_DOMAIN = "apex_domain"
    EXACT_HOST_DOMAIN_ATTRIBUTE = "exact_host_domain_attribute"
    PUBLIC_SUFFIX_INVALID = "public_suffix_invalid"


@dataclass(frozen=True)
class DomainResult:
    status: DomainStatus
    confidence: Confidence
    cookie_name: str
    raw_set_cookie: str
    scope_issue: Optional[ScopeIssue] = field(default=None)


def classify_cookie(
    cookie: ParsedCookie, *, host: str, sso_allowlisted: bool = False,
) -> DomainResult:
    if cookie.sensitivity == Sensitivity.LOW or sso_allowlisted:
        return DomainResult(
            status=DomainStatus.NOT_APPLICABLE, confidence="high",
            cookie_name=cookie.name, raw_set_cookie=cookie.raw_set_cookie,
        )
    domain = cookie.domain  # already leading-dot-stripped by parser
    if not domain:
        return DomainResult(
            status=DomainStatus.REJECTED, confidence="high",
            cookie_name=cookie.name, raw_set_cookie=cookie.raw_set_cookie,
        )
    if domain in _PUBLIC_SUFFIXES:
        return DomainResult(
            status=DomainStatus.REJECTED, confidence="high",
            cookie_name=cookie.name, raw_set_cookie=cookie.raw_set_cookie,
            scope_issue=ScopeIssue.PUBLIC_SUFFIX_INVALID,
        )
    # domain is a suffix of host (parent-domain scope)
    if host.endswith("." + domain):
        return DomainResult(
            status=DomainStatus.CONFIRMED, confidence="high",
            cookie_name=cookie.name, raw_set_cookie=cookie.raw_set_cookie,
            scope_issue=ScopeIssue.PARENT_DOMAIN,
        )
    if domain == host:
        # apex host (2 labels, e.g. "example.test") with domain= matching self
        if host.count(".") == 1:
            return DomainResult(
                status=DomainStatus.CANDIDATE, confidence="medium",
                cookie_name=cookie.name, raw_set_cookie=cookie.raw_set_cookie,
                scope_issue=ScopeIssue.APEX_DOMAIN,
            )
        return DomainResult(
            status=DomainStatus.CANDIDATE, confidence="low",
            cookie_name=cookie.name, raw_set_cookie=cookie.raw_set_cookie,
            scope_issue=ScopeIssue.EXACT_HOST_DOMAIN_ATTRIBUTE,
        )
    return DomainResult(
        status=DomainStatus.REJECTED, confidence="high",
        cookie_name=cookie.name, raw_set_cookie=cookie.raw_set_cookie,
    )
