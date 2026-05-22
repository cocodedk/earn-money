"""RoE (Rules of Engagement) dataclass — parsed from `roe.md`.

Per-program technique-level authority loaded at runtime by active
runners. The fields here mirror v1's archived `roe.md` schema; v2
treats this as an additive, append-only contract — new techniques
are added as nullable defaults so old `roe.md` files keep parsing.

The repo-wide floor (no DoS / no destructive / no social engineering
/ PII synthetic-only) applies whenever a field is unset; any field
explicitly set in `roe.md` overrides the floor *for that program*.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RoE:
    """Parsed `roe.md` frontmatter."""
    max_requests_per_second: int
    dos_authorized: bool = False
    destructive_payloads_authorized: bool = False
    social_engineering_authorized: bool = False
    pii_handling: str = "one_redacted_screenshot"
    authorized_test_environments: list[str] = field(default_factory=list)
    authorized_test_accounts: list[str] = field(default_factory=list)
    special_notes: str = ""
    # Phase 2 active-probe gates. All default False so a program never
    # implicitly authorises active auth-flow probing — the operator must
    # opt in per-flow by editing roe.md.
    allow_active_login_probes: bool = False
    allow_password_reset_probes: bool = False
    allow_mfa_probes: bool = False
    allow_oauth_probes: bool = False
    allow_registration_probes: bool = False
