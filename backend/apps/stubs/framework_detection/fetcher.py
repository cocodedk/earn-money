"""HTTP fetcher + evidence extractor for framework-detection.

Passive only — the spec restricts traffic to GET / and HEAD / plus
GET on /robots.txt, /sitemap.xml, /favicon.ico, and linked JS/CSS.
No POST, no form submission, no payload injection.

For the MVP runner we fetch the root document and extract:
- response headers (case-insensitive dict)
- response cookies (list of {name, value})
- HTML body (string)
- script src basenames (for the Angular SPA bundle-shape signature)

Other evidence sources from the spec (favicon hash, JS/CSS body
content, sitemap markers) land here as the signature library grows.
"""
from __future__ import annotations

import os
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup

from .matcher import EvidenceBundle


# Verify TLS by default. For local dev against self-signed certs (e.g.,
# an operator's lab fixture), the operator can set
# `FRAMEWORK_DETECTION_VERIFY=0` in their env to override.
DEFAULT_VERIFY = os.environ.get("FRAMEWORK_DETECTION_VERIFY", "1") != "0"

# Short timeout — frontend perceives slow scans as broken; cookbook
# targets are local-network for fixtures, ~ms-scale.
DEFAULT_TIMEOUT = 10.0


def fetch_evidence(base_url: str) -> EvidenceBundle:
    """Fetch the target's root document and decompose into evidence."""
    with httpx.Client(
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
        verify=DEFAULT_VERIFY,
    ) as client:
        response = client.get(base_url)

    soup = BeautifulSoup(response.text or "", "html.parser")
    script_names = []
    for tag in soup.find_all("script", src=True):
        src = tag.get("src", "")
        script_names.append(_basename(src))

    return {
        "headers": dict(response.headers),
        "cookies": [
            {"name": cookie.name, "value": cookie.value}
            for cookie in response.cookies.jar
        ],
        "html_body": response.text or "",
        "script_names": script_names,
        "url": str(response.url),
        "status_code": response.status_code,
    }


def _basename(url_or_path: str) -> str:
    """Return the filename portion of a script src.

    Examples:
      "/static/main.123abc.js"     → "main.123abc.js"
      "https://cdn.example/a.js"   → "a.js"
      "main.js"                    → "main.js"
    """
    if "://" in url_or_path:
        path = urlsplit(url_or_path).path
    else:
        path = url_or_path
    last = path.rsplit("/", 1)[-1]
    return last
