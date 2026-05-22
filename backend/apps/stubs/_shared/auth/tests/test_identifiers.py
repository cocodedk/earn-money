"""Contract tests for `_shared/auth/identifiers.generate_invalid_identifier`.

Coverage matrix per [[plan shared-infra D]]:
- `kind="email"` returns `scanner-<nonce>@example.invalid`.
- `kind="username"` returns `scanner_invalid_<nonce>`.
- Auto-generated nonces are 16 lowercase hex chars and unique per call.
- Explicit nonce is preserved when valid.
- Invalid `kind` raises ValueError.
- Invalid nonce characters raise ValueError.
- Non-ASCII / non-hex nonce raises ValueError.
"""
from __future__ import annotations

import re

import pytest

from apps.stubs._shared.auth.identifiers import generate_invalid_identifier


EMAIL_RE = re.compile(r"^scanner-[0-9a-f]+@example\.invalid$")
USERNAME_RE = re.compile(r"^scanner_invalid_[0-9a-f]+$")


def test_email_default_format() -> None:
    out = generate_invalid_identifier("email")
    assert EMAIL_RE.match(out), out


def test_username_default_format() -> None:
    out = generate_invalid_identifier("username")
    assert USERNAME_RE.match(out), out


def test_username_starts_with_scanner_invalid_prefix() -> None:
    """The `scanner_invalid_` prefix is the safety contract — it makes
    every scanner-generated username visible to defender logs as a
    scanner trace, not hostile traffic. Locked in here so a regex
    refactor in identifiers.py can't silently break the prefix."""
    out = generate_invalid_identifier("username")
    assert out.startswith("scanner_invalid_"), out


def test_email_starts_with_scanner_prefix_under_example_invalid() -> None:
    """Mirror contract for the email path: `scanner-` prefix +
    `@example.invalid` suffix (RFC 6761 reserved → no real recipient)."""
    out = generate_invalid_identifier("email")
    assert out.startswith("scanner-"), out
    assert out.endswith("@example.invalid"), out


def test_auto_nonce_length() -> None:
    out = generate_invalid_identifier("email")
    nonce = out[len("scanner-"):-len("@example.invalid")]
    assert len(nonce) == 16
    assert all(c in "0123456789abcdef" for c in nonce)


def test_two_auto_nonces_differ() -> None:
    a = generate_invalid_identifier("email")
    b = generate_invalid_identifier("email")
    assert a != b


def test_explicit_nonce_preserved() -> None:
    out = generate_invalid_identifier("username", nonce="deadbeef")
    assert out == "scanner_invalid_deadbeef"


def test_explicit_nonce_lowercased() -> None:
    out = generate_invalid_identifier("username", nonce="DEADBEEF")
    assert out == "scanner_invalid_deadbeef"


def test_invalid_kind_raises() -> None:
    with pytest.raises(ValueError, match="kind"):
        generate_invalid_identifier("password")  # type: ignore[arg-type]


def test_empty_explicit_nonce_raises() -> None:
    with pytest.raises(ValueError, match="nonce"):
        generate_invalid_identifier("email", nonce="")


def test_nonce_too_long_raises() -> None:
    with pytest.raises(ValueError, match="nonce"):
        generate_invalid_identifier("email", nonce="a" * 33)


def test_nonce_with_at_sign_raises() -> None:
    with pytest.raises(ValueError, match="nonce"):
        generate_invalid_identifier("email", nonce="bad@nonce")


def test_nonce_with_whitespace_raises() -> None:
    with pytest.raises(ValueError, match="nonce"):
        generate_invalid_identifier("email", nonce="bad nonce")


def test_nonce_with_slash_raises() -> None:
    with pytest.raises(ValueError, match="nonce"):
        generate_invalid_identifier("email", nonce="bad/nonce")


def test_nonce_with_unicode_raises() -> None:
    with pytest.raises(ValueError, match="nonce"):
        generate_invalid_identifier("email", nonce="déadbeef")


def test_nonce_with_uppercase_hex_is_accepted() -> None:
    """Uppercase hex is normalized, not rejected — operator-friendly."""
    out = generate_invalid_identifier("email", nonce="DEADBEEF")
    assert out == "scanner-deadbeef@example.invalid"


def test_nonce_with_non_hex_raises() -> None:
    with pytest.raises(ValueError, match="nonce"):
        generate_invalid_identifier("email", nonce="g00dnonce")
