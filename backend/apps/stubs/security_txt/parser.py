"""security.txt line parser for stub 1.13.

Spec §Parsing: case-insensitive field names, repeated fields kept
as ordered tuples, unknown fields preserved with original casing,
comments + blank lines skipped, malformed lines recorded as
parse_errors (don't crash the scan).

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/13-security-txt.md
"""
from __future__ import annotations

from dataclasses import dataclass, field


# Spec §Parsing recognized field list. Lowercased for the
# case-insensitive match; original casing surfaces in unknown_fields
# for fields we don't recognise.
_KNOWN_FIELDS: frozenset[str] = frozenset({
    "contact",
    "expires",
    "encryption",
    "acknowledgments",
    "preferred-languages",
    "canonical",
    "policy",
    "hiring",
    "csaf",
})


@dataclass(frozen=True)
class ParsedSecurityTxt:
    contact: tuple[str, ...] = field(default_factory=tuple)
    expires: tuple[str, ...] = field(default_factory=tuple)
    encryption: tuple[str, ...] = field(default_factory=tuple)
    acknowledgments: tuple[str, ...] = field(default_factory=tuple)
    preferred_languages: tuple[str, ...] = field(default_factory=tuple)
    canonical: tuple[str, ...] = field(default_factory=tuple)
    policy: tuple[str, ...] = field(default_factory=tuple)
    hiring: tuple[str, ...] = field(default_factory=tuple)
    csaf: tuple[str, ...] = field(default_factory=tuple)
    # (original-case name, value) pairs for fields we don't recognise.
    unknown_fields: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    parse_errors: tuple[str, ...] = field(default_factory=tuple)


def parse_security_txt(body: str) -> ParsedSecurityTxt:
    """Parse `body` line-by-line. Always returns a ParsedSecurityTxt;
    malformed input produces parse_errors entries rather than raising."""
    if not body:
        return ParsedSecurityTxt()

    known: dict[str, list[str]] = {f: [] for f in _KNOWN_FIELDS}
    unknown: list[tuple[str, str]] = []
    errors: list[str] = []

    for lineno, raw in enumerate(body.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            errors.append(f"line {lineno}: malformed (no colon): {stripped!r}")
            continue
        name, _, value = stripped.partition(":")
        name = name.strip()
        value = value.strip()
        if not value:
            errors.append(f"line {lineno}: empty value for field {name!r}")
            continue
        lowered = name.lower()
        if lowered in _KNOWN_FIELDS:
            known[lowered].append(value)
        else:
            unknown.append((name, value))

    return ParsedSecurityTxt(
        contact=tuple(known["contact"]),
        expires=tuple(known["expires"]),
        encryption=tuple(known["encryption"]),
        acknowledgments=tuple(known["acknowledgments"]),
        preferred_languages=tuple(known["preferred-languages"]),
        canonical=tuple(known["canonical"]),
        policy=tuple(known["policy"]),
        hiring=tuple(known["hiring"]),
        csaf=tuple(known["csaf"]),
        unknown_fields=tuple(unknown),
        parse_errors=tuple(errors),
    )
