"""Header-source signatures.

`field` names the (lowercased) HTTP header to inspect; value_pattern +
match_type select how to compare against that header's value across
all probes' responses.
"""
from __future__ import annotations

from typing import Any


HEADER_SIGNATURES: list[dict[str, Any]] = [
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
]
