"""Signature library for stub 1.4 backend-hints.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/04-backend-hints.md
"""
from __future__ import annotations

from typing import Any


CATEGORIES: set[str] = {
    "app_framework",
    "app_runtime",
    "session_marker",
    "error_page",
    "unknown",
}

MATCH_SOURCES: set[str] = {
    "header",
    "cookie",
    "body",
}


# Headers: signature.value_pattern matches the value of signature.field
# header. Cookies: signature.value_pattern matches the cookie *name*
# (not value — values are sensitive and redacted). Bodies: signature
# .value_pattern matches the body text of any probe.
SIGNATURES: list[dict[str, Any]] = [
    # Cookies — session-name fingerprints
    {
        "id": "cookie_connect_sid_express",
        "technology": "Express",
        "category": "app_framework",
        "source": "cookie",
        "match_type": "exact",
        "value_pattern": "connect.sid",
        "version_regex": None,
        "confidence": "high",
    },
    {
        "id": "cookie_csrftoken_django",
        "technology": "Django",
        "category": "app_framework",
        "source": "cookie",
        "match_type": "exact",
        "value_pattern": "csrftoken",
        "version_regex": None,
        "confidence": "high",
    },
    {
        "id": "cookie_sessionid_django",
        "technology": "Django",
        "category": "session_marker",
        "source": "cookie",
        "match_type": "exact",
        "value_pattern": "sessionid",
        "version_regex": None,
        "confidence": "medium",
    },
    {
        "id": "cookie_jsessionid_java",
        "technology": "Java Servlet",
        "category": "app_runtime",
        "source": "cookie",
        "match_type": "exact",
        "value_pattern": "JSESSIONID",
        "version_regex": None,
        "confidence": "high",
    },
    {
        "id": "cookie_aspnet_session",
        "technology": "ASP.NET",
        "category": "app_framework",
        "source": "cookie",
        "match_type": "exact",
        "value_pattern": "ASP.NET_SessionId",
        "version_regex": None,
        "confidence": "high",
    },
    {
        "id": "cookie_aspnet_core",
        "technology": "ASP.NET",
        "category": "app_framework",
        "source": "cookie",
        "match_type": "regex",
        "value_pattern": r"^\.AspNetCore\.",
        "version_regex": None,
        "confidence": "high",
    },
    {
        "id": "cookie_laravel_session",
        "technology": "Laravel",
        "category": "app_framework",
        "source": "cookie",
        "match_type": "exact",
        "value_pattern": "laravel_session",
        "version_regex": None,
        "confidence": "high",
    },
    {
        "id": "cookie_phpsessid",
        "technology": "PHP",
        "category": "app_runtime",
        "source": "cookie",
        "match_type": "exact",
        "value_pattern": "PHPSESSID",
        "version_regex": None,
        "confidence": "high",
    },
    # Headers — explicit X-Powered-By + version
    {
        "id": "header_powered_by_express",
        "technology": "Express",
        "category": "app_framework",
        "source": "header",
        "field": "x-powered-by",
        "match_type": "contains",
        "value_pattern": "Express",
        "version_regex": None,
        "confidence": "high",
    },
    {
        "id": "header_powered_by_php",
        "technology": "PHP",
        "category": "app_runtime",
        "source": "header",
        "field": "x-powered-by",
        "match_type": "contains",
        "value_pattern": "PHP",
        "version_regex": r"PHP/([0-9.]+)",
        "confidence": "high",
    },
    {
        "id": "header_aspnet_version",
        "technology": "ASP.NET",
        "category": "app_framework",
        "source": "header",
        "field": "x-aspnet-version",
        "match_type": "regex",
        "value_pattern": r".+",
        "version_regex": r"^([0-9.]+)$",
        "confidence": "high",
    },
    {
        "id": "header_server_werkzeug",
        "technology": "Werkzeug",
        "category": "app_runtime",
        "source": "header",
        "field": "server",
        "match_type": "contains",
        "value_pattern": "Werkzeug",
        "version_regex": r"Werkzeug/([0-9.]+)",
        "confidence": "high",
    },
    # Bodies — error-page markers
    {
        "id": "body_whitelabel_error",
        "technology": "Spring Boot",
        "category": "error_page",
        "source": "body",
        "match_type": "contains",
        "value_pattern": "Whitelabel Error Page",
        "version_regex": None,
        "confidence": "high",
    },
    {
        "id": "body_django_debug",
        "technology": "Django",
        "category": "error_page",
        "source": "body",
        "match_type": "contains",
        "value_pattern": "DisallowedHost at",
        "version_regex": None,
        "confidence": "high",
    },
    {
        "id": "body_werkzeug_debugger",
        "technology": "Werkzeug",
        "category": "error_page",
        "source": "body",
        "match_type": "contains",
        "value_pattern": "Werkzeug Debugger",
        "version_regex": None,
        "confidence": "high",
    },
]
