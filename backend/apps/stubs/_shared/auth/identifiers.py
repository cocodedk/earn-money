"""Synthetic invalid-control identifiers for Phase 2 active probes.

Every Phase 2 stub that submits an identifier to a real endpoint MUST
get the invalid-control value from this module. The shape is fixed:

* Email: `scanner-<nonce>@example.invalid` — `example.invalid` is
  RFC 6761 reserved, so no DNS resolution can ever route email to a
  real user.
* Username: `scanner_invalid_<nonce>` — the `scanner_invalid_` prefix
  is visible in defender logs and clearly identifies the trace as a
  scanner probe, not a hostile attacker brute-forcing `admin`/`test`.

Nonces are 16 lowercase hex chars when auto-generated; callers may
inject a deterministic nonce for tests but the helper still validates
it (`^[0-9a-f]{1,32}$` after lowercasing).
"""
from __future__ import annotations

import re
import secrets
from typing import Literal


Kind = Literal["email", "username"]

_NONCE_RE = re.compile(r"^[0-9a-f]{1,32}$")
_VALID_KINDS: tuple[Kind, ...] = ("email", "username")


def generate_invalid_identifier(
    kind: Kind, *, nonce: str | None = None,
) -> str:
    """Return a synthetic invalid identifier of the requested ``kind``.

    Raises:
        ValueError: when ``kind`` is unknown or ``nonce`` is non-hex /
            empty / too long / contains whitespace, ``@``, ``/``, or
            non-ASCII characters.
    """
    if kind not in _VALID_KINDS:
        raise ValueError(
            f"kind must be one of {_VALID_KINDS!r}; got {kind!r}"
        )
    if nonce is None:
        nonce = secrets.token_hex(8)
    else:
        nonce = _validate_nonce(nonce)
    if kind == "email":
        return f"scanner-{nonce}@example.invalid"
    return f"scanner_invalid_{nonce}"


def _validate_nonce(nonce: str) -> str:
    """Lowercase and validate a caller-supplied nonce."""
    if not nonce:
        raise ValueError("nonce must be non-empty")
    lowered = nonce.lower()
    if not _NONCE_RE.match(lowered):
        raise ValueError(
            f"nonce must match {_NONCE_RE.pattern}; got {nonce!r}"
        )
    return lowered
