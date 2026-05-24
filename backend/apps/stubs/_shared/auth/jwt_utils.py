"""JWT decode, redact, fingerprint, and token-building helpers.

Pure functions — no I/O, no verification of signatures. Used by
JWT-family stubs (3.9-3.13) that need to decode tokens, build modified
tokens for active probes, and redact token values before persisting.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any, NamedTuple


class ParsedJwt(NamedTuple):
    header: dict[str, Any]
    payload: dict[str, Any]
    signature_present: bool


_HMAC_ALGOS: dict[str, str] = {
    "HS256": "sha256",
    "HS384": "sha384",
    "HS512": "sha512",
}


def parse_jwt(token: str) -> ParsedJwt | None:
    """Decode a JWT without verifying the signature.

    Returns ParsedJwt or None when the string is not a valid three-part JWT.
    """
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        header = json.loads(_b64url_decode(parts[0]))
        payload = json.loads(_b64url_decode(parts[1]))
    except Exception:
        return None
    return ParsedJwt(
        header=header,
        payload=payload,
        signature_present=bool(parts[2]),
    )


def redact_token(token: str) -> str:
    """Return a safe display form — first 8 chars + '...'."""
    return token[:8] + "..."


def fingerprint_token(token: str) -> str:
    """Return the first 16 hex chars of the SHA-256 of the raw token."""
    return hashlib.sha256(token.encode()).hexdigest()[:16]


def build_alg_none_token(header: dict[str, Any], payload: dict[str, Any]) -> str:
    """Build an unsigned JWT with alg=none and an empty signature."""
    modified_header = {**header, "alg": "none"}
    h = _b64url_encode(json.dumps(modified_header, separators=(",", ":")))
    p = _b64url_encode(json.dumps(payload, separators=(",", ":")))
    return f"{h}.{p}."


def build_hs_token(
    header: dict[str, Any],
    payload: dict[str, Any],
    secret: bytes,
    alg: str,
) -> str:
    """Build an HMAC-signed JWT using the given algorithm and secret.

    Raises ValueError for non-HMAC algorithms.
    """
    if alg not in _HMAC_ALGOS:
        raise ValueError(f"Unsupported algorithm for HMAC signing: {alg!r}")
    hash_name = _HMAC_ALGOS[alg]
    modified_header = {**header, "alg": alg}
    h = _b64url_encode(json.dumps(modified_header, separators=(",", ":")))
    p = _b64url_encode(json.dumps(payload, separators=(",", ":")))
    signing_input = f"{h}.{p}".encode()
    sig_bytes = hmac.new(secret, signing_input, hash_name).digest()
    sig = base64.urlsafe_b64encode(sig_bytes).rstrip(b"=").decode()
    return f"{h}.{p}.{sig}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _b64url_decode(segment: str) -> bytes:
    padding = 4 - len(segment) % 4
    if padding != 4:
        segment += "=" * padding
    return base64.urlsafe_b64decode(segment)


def _b64url_encode(data: str) -> str:
    return base64.urlsafe_b64encode(data.encode()).rstrip(b"=").decode()
