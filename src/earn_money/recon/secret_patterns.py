"""Regex catalogue for high-value leaked-secret detection.

Patterns are deliberately conservative: each one matches a *specific*
provider format with a long-enough random tail to keep false positives
low. Generic `api_key = "..."` literals are intentionally NOT here —
those flow through nuclei's `credentials-disclosure` template and are
filtered by `triage_rules.yaml`.

Severity assignments map to operator-actionability:

- `critical` — terminal compromise of the issuing system (private keys).
- `high`     — direct admin-equivalent access to a vendor account.
- `medium`   — credential of unknown blast radius (JWT, opaque tokens).
- (No `low` / `info` entries here — anything noisier belongs in
  nuclei's exposure templates, not this curated set.)
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SecretMatch:
    pattern_name: str
    severity: str
    value: str
    start: int


@dataclass(frozen=True)
class _Pattern:
    name: str
    severity: str
    regex: re.Pattern[str]


_PATTERNS: tuple[_Pattern, ...] = (
    _Pattern(
        name="aws_access_key",
        severity="high",
        regex=re.compile(r"AKIA[0-9A-Z]{16}"),
    ),
    _Pattern(
        name="github_pat",
        severity="high",
        # Classic / fine-grained / OAuth / refresh / server-to-server prefixes.
        regex=re.compile(r"gh[opusr]_[A-Za-z0-9]{36,255}"),
    ),
    _Pattern(
        name="slack_token",
        severity="high",
        regex=re.compile(r"xox[bpoasrlt]-[0-9A-Za-z-]{20,200}"),
    ),
    _Pattern(
        name="stripe_live_key",
        severity="high",
        regex=re.compile(r"sk_live_[A-Za-z0-9]{24,99}"),
    ),
    _Pattern(
        name="google_api_key",
        severity="high",
        regex=re.compile(r"AIza[A-Za-z0-9_-]{35}"),
    ),
    _Pattern(
        name="jwt",
        severity="medium",
        # Three base64url segments separated by '.'; payload starts with 'eyJ'.
        regex=re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{20,}"),
    ),
    _Pattern(
        name="private_key_block",
        severity="critical",
        regex=re.compile(
            r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"
        ),
    ),
)


def find_secrets(text: str) -> list[SecretMatch]:
    """Scan `text` against every pattern. Returns each match exactly once.

    Patterns are mutually-exclusive enough at the regex level that we
    don't bother deduplicating across pattern boundaries; if a string
    happens to match two patterns (rare), both are reported and the
    operator decides.
    """
    out: list[SecretMatch] = []
    for pat in _PATTERNS:
        for m in pat.regex.finditer(text):
            out.append(SecretMatch(
                pattern_name=pat.name,
                severity=pat.severity,
                value=m.group(0),
                start=m.start(),
            ))
    return out


def redact(value: str) -> str:
    """Keep the first 4 and last 2 characters; ellipsis in the middle.

    Used by callers when embedding a matched secret in a Signal's
    payload — we want the operator to recognize it without storing the
    plaintext.
    """
    if len(value) < 8:
        return "…"
    return f"{value[:4]}…{value[-2:]}"
