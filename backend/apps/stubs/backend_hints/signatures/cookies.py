"""Cookie-source signatures.

Cookies match on NAME only — values are sensitive and the fetcher
redacts them before persistence. value_pattern carries the name
pattern; match_type selects exact / contains / regex semantics on
that name.
"""
from __future__ import annotations

from typing import Any


COOKIE_SIGNATURES: list[dict[str, Any]] = [
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
]
