"""Shared cookie-attribute parser for Phase-3 session-management stubs."""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from apps.stubs._shared.hashing import body_hash


class Sensitivity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CookieCategory(str, Enum):
    SESSION = "session"
    AUTH = "auth"
    ACCESS_TOKEN = "access_token"
    REFRESH_TOKEN = "refresh_token"
    REMEMBER_ME = "remember_me"
    FRAMEWORK_SESSION = "framework_session"
    CSRF_SESSION = "csrf_session"
    UNKNOWN = "unknown"


_FRAMEWORK_NAMES: frozenset[str] = frozenset({
    "PHPSESSID", "JSESSIONID", "connect.sid", "ASP.NET_SessionId",
    "ASP_NET_SessionId", "ASPSESSIONID",
})
_HIGH_NAMES: frozenset[str] = frozenset({
    "session", "sid", "auth", "access_token", "refresh_token",
    "id_token", "jwt", "token",
})
_HIGH_NAMES_LOWER: frozenset[str] = frozenset(n.lower() for n in _HIGH_NAMES)
_MEDIUM_PATTERN = re.compile(
    r"(session|sess|auth|token|login|remember|sso)", re.IGNORECASE
)
_CSRF_PATTERN = re.compile(r"csrf", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedCookie:
    name: str
    value_redacted: Optional[str]
    domain: Optional[str]
    path: Optional[str]
    expires: Optional[str]
    max_age: Optional[int]
    secure: bool
    httponly: bool
    samesite: Optional[str]
    sensitivity: Sensitivity
    category: CookieCategory
    raw_set_cookie: str


def parse_set_cookie(header: str) -> ParsedCookie:
    parts = [p.strip() for p in header.split(";")]
    name_val = parts[0]
    name, _, raw_value = name_val.partition("=")
    name = name.strip()
    value_redacted = _redact(raw_value.strip()) if raw_value else None

    attrs: dict[str, Optional[str]] = {}
    for part in parts[1:]:
        key, _, val = part.partition("=")
        attrs[key.strip().lower()] = val.strip() if val else None

    domain_raw = attrs.get("domain")
    domain = domain_raw.lstrip(".") if domain_raw else None

    max_age_raw = attrs.get("max-age")
    max_age: Optional[int] = None
    if max_age_raw is not None:
        try:
            max_age = int(max_age_raw)
        except ValueError:
            pass

    return ParsedCookie(
        name=name,
        value_redacted=value_redacted,
        domain=domain,
        path=attrs.get("path"),
        expires=attrs.get("expires"),
        max_age=max_age,
        secure="secure" in attrs,
        httponly="httponly" in attrs,
        samesite=attrs.get("samesite"),
        sensitivity=is_sensitive_cookie(name),
        category=_classify_category(name),
        raw_set_cookie=_redact_header(header),
    )


def is_sensitive_cookie(name: str) -> Sensitivity:
    if name in _FRAMEWORK_NAMES:
        return Sensitivity.HIGH
    if name.lower() in _HIGH_NAMES_LOWER:
        return Sensitivity.HIGH
    if _CSRF_PATTERN.search(name):
        return Sensitivity.LOW
    if _MEDIUM_PATTERN.search(name):
        return Sensitivity.MEDIUM
    return Sensitivity.LOW


def _classify_category(name: str) -> CookieCategory:
    if name in _FRAMEWORK_NAMES:
        return CookieCategory.FRAMEWORK_SESSION
    nl = name.lower()
    if nl in ("session", "sid"):
        return CookieCategory.SESSION
    if nl == "auth":
        return CookieCategory.AUTH
    if nl == "access_token":
        return CookieCategory.ACCESS_TOKEN
    if nl == "refresh_token":
        return CookieCategory.REFRESH_TOKEN
    if "remember" in nl:
        return CookieCategory.REMEMBER_ME
    if _CSRF_PATTERN.search(name):
        return CookieCategory.CSRF_SESSION
    if _MEDIUM_PATTERN.search(name):
        return CookieCategory.SESSION
    return CookieCategory.UNKNOWN


def _redact(value: str) -> str:
    h = body_hash(value)[:8]
    return f"<redacted:{h}>"


def _redact_header(header: str) -> str:
    parts = header.split(";")
    name_val = parts[0]
    name, _, _ = name_val.partition("=")
    return name.strip() + "=<redacted>;" + ";".join(parts[1:])
