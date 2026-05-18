"""Per-field validators for POST /api/probe/start.

Extracted from _server_probe_start.py to keep both files under the
project's 200-line cap. Every validator takes the parsed JSON body and
a Responder, emits a 400 on rejection, and returns either the cleaned
value or None (or a sentinel tuple) to signal that the caller should
return.
"""
from __future__ import annotations

import ipaddress
import json
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

from earn_money import config

# Networks the dashboard refuses as a defence-in-depth fast-fail.
# Authoritative enforcement lives in ScopePolicy at HTTP-request time.
_PRIVATE_RESERVED_NETS = (
    "127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
    "169.254.0.0/16", "224.0.0.0/4", "::1/128", "fc00::/7", "fe80::/10",
)


class Responder(Protocol):
    def send_json(self, status: int, payload: dict[str, Any]) -> None: ...
    def read_body(self) -> bytes: ...


def parse_request_body(r: Responder) -> dict[str, Any] | None:
    try:
        parsed: dict[str, Any] = json.loads(r.read_body() or b"{}")
    except json.JSONDecodeError:
        r.send_json(400, {"error": "invalid JSON body"})
        return None
    return parsed


def validate_base_url(payload: dict[str, Any], r: Responder) -> str | None:
    """Return the cleaned base_url or None (and emit 400) on rejection."""
    base_url = payload.get("base_url")
    if not isinstance(base_url, str) or not base_url.strip():
        r.send_json(400, {"error": "base_url required"})
        return None
    base_url = base_url.strip().rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https"):
        r.send_json(400, {"error":
            f"base_url scheme must be http or https, got {parsed.scheme!r}"})
        return None
    if parsed.username or parsed.password:
        r.send_json(400, {"error":
            "base_url must not contain userinfo (user:pass@)"})
        return None
    if not parsed.hostname:
        r.send_json(400, {"error": "base_url missing host"})
        return None
    host_lower = parsed.hostname.lower()
    if host_lower in ("localhost", "0.0.0.0", "::", "::1"):
        r.send_json(400, {"error":
            f"base_url host {parsed.hostname!r} is loopback/unspecified"})
        return None
    try:
        addr = ipaddress.ip_address(host_lower)
        for net_cidr in _PRIVATE_RESERVED_NETS:
            if addr in ipaddress.ip_network(net_cidr):
                r.send_json(400, {"error":
                    f"base_url host {parsed.hostname!r} is private/reserved"})
                return None
    except ValueError:
        pass  # hostname (not an IP literal) — fine, let runtime ScopePolicy enforce
    return base_url


def validate_target(payload: dict[str, Any], r: Responder) -> tuple[str, str, str | None] | None:
    """Return (target_kind, platform, program) or None on rejection.

    `target_kind` is required and explicit — removes the prior ambiguity
    where omitting `program` silently skipped FROZEN.
    """
    target_kind = payload.get("target_kind")
    if target_kind not in ("local_lab", "registered_program"):
        r.send_json(400, {"error":
            "target_kind must be 'local_lab' or 'registered_program'"})
        return None
    platform = payload.get("platform", "local")
    program = payload.get("program")
    if platform in ("", None):
        platform = "local"
    if program == "":
        program = None
    if not isinstance(platform, str):
        r.send_json(400, {"error": "platform must be a string"})
        return None
    if program is not None and not isinstance(program, str):
        r.send_json(400, {"error": "program must be a string"})
        return None
    # registered_program REQUIRES program (the FROZEN gate depends on
    # it). local_lab MAY omit program — FROZEN is skipped for local-lab
    # targets by design, but RoE / ScopePolicy still enforce
    # allowed_hosts at request time.
    if target_kind == "registered_program" and not program:
        r.send_json(400, {"error":
            "program required when target_kind=registered_program"})
        return None
    return target_kind, platform, program


def validate_max_turns(payload: dict[str, Any], r: Responder) -> tuple[bool, int | None]:
    """Return (ok, max_turns_or_None). `type(x) is int` rejects bool
    (which is a subclass of int — `isinstance(True, int)` is True, and
    `1 <= True <= 10000` is True too, so isinstance would silently
    accept max_turns=true).

    The form-level cap is high (10000) so the RoE profile's own
    max_turns is the real ceiling — ProbeRunner applies
    min(profile.max_turns, max_turns) so an unrestricted PoC RoE (e.g.
    juice-shop) can use higher values while tight-budgeted RoEs stay
    tight."""
    max_turns = payload.get("max_turns")
    if max_turns is None:
        return True, None
    if type(max_turns) is not int or not (1 <= max_turns <= 10000):
        r.send_json(400, {"error":
            "max_turns must be an int between 1 and 10000"})
        return False, None
    return True, max_turns


def resolve_roe_path(payload: dict[str, Any], paths: config.Paths) -> Path | None:
    roe_raw = payload.get("roe_profile")
    if isinstance(roe_raw, str) and roe_raw.strip():
        _rp = Path(roe_raw.strip())
        return _rp if _rp.is_absolute() else paths.root / _rp
    return None
