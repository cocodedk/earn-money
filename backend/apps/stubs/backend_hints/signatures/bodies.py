"""Body-source signatures.

Body matches operate on any probe's body text. The /__scanner_404_xxx
probe is the cheapest way to surface framework error-page markers
(Spring's Whitelabel, Werkzeug debugger) without probing admin paths
the spec forbids.
"""
from __future__ import annotations

from typing import Any


BODY_SIGNATURES: list[dict[str, Any]] = [
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
        # Tomcat's default 4xx/5xx error page. Surfaces the runtime
        # even when the upstream app strips X-Powered-By — Tomcat
        # generates these directly. The trailing slash is the version
        # separator (e.g. "Apache Tomcat/9.0.85"); requiring it narrows
        # the match away from docs/release-note pages that mention
        # "Apache Tomcat" in prose.
        "id": "body_tomcat_error",
        "technology": "Apache Tomcat",
        "category": "app_runtime",
        "source": "body",
        "match_type": "contains",
        "value_pattern": "Apache Tomcat/",
        "version_regex": r"Apache Tomcat/([0-9.]+)",
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
