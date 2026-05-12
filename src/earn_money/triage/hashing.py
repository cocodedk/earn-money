"""Finding-hash composition + URL/host normalization.

The hash is sha256 over a canonical string:

    v1|<platform>|<slug>|<vuln_class>|<asset>|<target>|<signature>

The hash deliberately omits run_id, evidence path, title, severity, and
timestamps so a re-observation of the same finding by a later run produces
the same hash and refreshes the existing row rather than creating a duplicate.

Normalization decisions (see spec section 4):
- Scheme + host: lowercased.
- Path: case preserved (many web servers route case-sensitively).
- IDN: encoded via stdlib `encodings.idna`. UTS-46 / PyPI `idna` is *not*
  pulled in because Phase 3b only handles ASCII hostnames; add when needed.
  If an IDN scope is onboarded later, expect hash churn — existing findings
  may need a one-time migration.
"""

from __future__ import annotations

import hashlib
from urllib.parse import (
    quote,
    unquote,
    urlsplit,
    urlunsplit,
)

_DEFAULT_PORTS: dict[str, int] = {"http": 80, "https": 443}
_HASH_VERSION = "v1"


def normalize_asset(raw: str) -> str:
    """Lowercase the host. Accepts either a bare hostname or a URL."""
    host = urlsplit(raw).hostname or "" if "://" in raw else raw
    return _encode_host(host)


def _encode_host(host: str) -> str:
    host = host.lower().strip(".")
    if not host:
        return ""
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError:
        return host


def normalize_target(raw: str) -> str:
    """Apply normalization rules 1-7. Non-URL input collapses to ``normalize_asset``."""
    if "://" not in raw:
        return normalize_asset(raw)
    parts = urlsplit(raw)
    scheme = parts.scheme.lower()
    host = _encode_host(parts.hostname or "")
    netloc = _build_netloc(scheme, host, parts.port)
    path = _normalize_path(parts.path)
    query = _normalize_query(parts.query)
    return urlunsplit((scheme, netloc, path, query, ""))


def _build_netloc(scheme: str, host: str, port: int | None) -> str:
    if port is None or port == _DEFAULT_PORTS.get(scheme):
        return host
    return f"{host}:{port}"


def _normalize_path(path: str) -> str:
    if not path:
        return "/"
    parts: list[str] = []
    for segment in path.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if parts:
                parts.pop()
            continue
        parts.append(segment)
    cleaned = "/" + "/".join(parts)
    return quote(unquote(cleaned), safe="/")


def _normalize_query(query: str) -> str:
    if not query:
        return ""
    # Split into raw tokens to distinguish valueless (?debug) from empty-value (?empty=).
    # parse_qsl cannot tell them apart; we must handle them from the raw string.
    valueless: list[str] = []
    valued: list[tuple[str, str]] = []
    for token in query.split("&"):
        if not token:
            continue
        if "=" not in token:
            valueless.append(token)
        else:
            k, _, v = token.partition("=")
            if v != "":
                valued.append((k, v))
            # empty-value params (k=) are dropped (not in allowlist logic here)
    valued.sort(key=lambda kv: (kv[0], kv[1]))
    parts: list[str] = [kv[0] + "=" + kv[1] for kv in valued]
    parts.extend(sorted(valueless))
    return "&".join(parts)


def compute_hash(
    *,
    platform: str,
    slug: str,
    vuln_class: str,
    asset: str,
    target: str,
    signature: str,
) -> str:
    canonical = "|".join((
        _HASH_VERSION, platform, slug, vuln_class,
        normalize_asset(asset),
        normalize_target(target),
        signature,
    ))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def signature_for_nuclei(
    *, template_id: str, matcher_name: str | None, extracted: str | None
) -> str:
    """nuclei signature: '<template_id>|<matcher_name>|<extracted_normalized>'."""
    matcher = matcher_name or ""
    extracted_norm = normalize_target(extracted) if extracted else ""
    return f"{template_id}|{matcher}|{extracted_norm}"


def signature_for_httpx_anomaly(
    *, signal_type: str, old_fingerprint: str, new_fingerprint: str
) -> str:
    """httpx anomaly signature: <signal_type>|<old12>|<new12>."""
    return (
        f"{signal_type}|"
        f"{_short_hash(old_fingerprint)}|"
        f"{_short_hash(new_fingerprint)}"
    )


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
