"""Signature library for framework-detection (cookbook stub 1.1 §Detection logic).

The 9 signatures below mirror the YAML in the spec verbatim. New
technology coverage means adding entries here; the matcher logic in
`matcher.py` is generic across signatures.

Schema (per the spec):
  id           unique string
  technology   what the match implies (PHP, Angular, …)
  category     runtime | backend_framework | frontend_framework | known_product
  source       cookie | header | html
  field        per-source field name (name, X-Powered-By, body, script_names)
  match_type   equals | contains | contains_all
  pattern      single string (equals/contains)
  patterns     list of strings (contains_all only)
  confidence   low | medium | high
"""
from __future__ import annotations

from typing import Any


SIGNATURES: list[dict[str, Any]] = [
    {
        "id": "cookie_php_session",
        "technology": "PHP",
        "category": "runtime",
        "source": "cookie",
        "field": "name",
        "match_type": "equals",
        "pattern": "PHPSESSID",
        "confidence": "high",
    },
    {
        "id": "cookie_java_session",
        "technology": "Java Servlet",
        "category": "runtime",
        "source": "cookie",
        "field": "name",
        "match_type": "equals",
        "pattern": "JSESSIONID",
        "confidence": "high",
    },
    {
        "id": "header_express",
        "technology": "Express",
        "category": "backend_framework",
        "source": "header",
        "field": "X-Powered-By",
        "match_type": "contains",
        "pattern": "Express",
        "confidence": "high",
    },
    {
        "id": "html_angular_marker",
        "technology": "Angular",
        "category": "frontend_framework",
        "source": "html",
        "field": "body",
        "match_type": "contains",
        "pattern": "ng-version",
        "confidence": "high",
    },
    {
        "id": "angular_bundle_shape",
        "technology": "Angular SPA",
        "category": "frontend_framework",
        "source": "html",
        "field": "script_names",
        "match_type": "contains_all",
        "patterns": ["runtime", "polyfills", "main"],
        "confidence": "medium",
    },
    {
        "id": "product_dvwa_marker",
        "technology": "DVWA",
        "category": "known_product",
        "source": "html",
        "field": "body",
        "match_type": "contains",
        "pattern": "Damn Vulnerable Web Application",
        "confidence": "high",
    },
    {
        "id": "product_webgoat_marker",
        "technology": "WebGoat",
        "category": "known_product",
        "source": "html",
        "field": "body",
        "match_type": "contains",
        "pattern": "WebGoat",
        "confidence": "high",
    },
    {
        "id": "product_juiceshop_marker",
        "technology": "OWASP Juice Shop",
        "category": "known_product",
        "source": "html",
        "field": "body",
        "match_type": "contains",
        "pattern": "OWASP Juice Shop",
        "confidence": "high",
    },
]
