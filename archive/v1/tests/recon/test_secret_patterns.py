"""Tests for the secret-pattern catalogue."""

from __future__ import annotations

import pytest

from earn_money.recon.secret_patterns import (
    SecretMatch,
    find_secrets,
    redact,
)


def test_find_aws_access_key() -> None:
    text = 'const k = "AKIAIOSFODNN7EXAMPLE";'
    sigs = find_secrets(text)
    assert len(sigs) == 1
    assert sigs[0].pattern_name == "aws_access_key"
    assert sigs[0].severity == "high"
    assert sigs[0].value == "AKIAIOSFODNN7EXAMPLE"


def test_find_github_pat_classic() -> None:
    text = 'TOKEN="ghp_" + "abcdef0123456789abcdef0123456789abcd";'
    # No match across concatenation — only literal forms.
    assert find_secrets(text) == []

    literal = 'const t = "ghp_abcdef0123456789abcdef0123456789abcd";'
    sigs = find_secrets(literal)
    assert len(sigs) == 1
    assert sigs[0].pattern_name == "github_pat"
    assert sigs[0].severity == "high"


def test_find_slack_token() -> None:
    text = 'WEBHOOK="xoxb-1234567890-1234567890123-abcdefABCDEF1234567890ab";'
    sigs = find_secrets(text)
    assert len(sigs) == 1
    assert sigs[0].pattern_name == "slack_token"
    assert sigs[0].severity == "high"


def test_find_stripe_live_key() -> None:
    text = 'STRIPE = "sk_live_aZbYcXdWeVfUgThSiRjQkPl1234567890ab";'
    sigs = find_secrets(text)
    assert any(s.pattern_name == "stripe_live_key" for s in sigs)


def test_find_google_api_key() -> None:
    text = 'apiKey: "AIzaSyD-EXAMPLE-EXAMPLE-EXAMPLE-EXAMPLE-X1"'
    sigs = find_secrets(text)
    assert any(s.pattern_name == "google_api_key" for s in sigs)


def test_find_jwt() -> None:
    text = (
        'const t = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.'
        'abcDEF123456abcDEF123456abcDEF123456abcDEF12";'
    )
    sigs = find_secrets(text)
    assert any(s.pattern_name == "jwt" for s in sigs)
    jwt = next(s for s in sigs if s.pattern_name == "jwt")
    assert jwt.severity == "medium"


def test_find_private_key_block() -> None:
    text = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA1234...\n"
        "-----END RSA PRIVATE KEY-----"
    )
    sigs = find_secrets(text)
    assert any(s.pattern_name == "private_key_block" for s in sigs)
    pkey = next(s for s in sigs if s.pattern_name == "private_key_block")
    assert pkey.severity == "critical"


def test_no_secrets_in_plain_text() -> None:
    assert find_secrets("This is a normal sentence with no keys.") == []


def test_multiple_secrets_in_one_text() -> None:
    text = (
        'const aws = "AKIAIOSFODNN7EXAMPLE";\n'
        'const gh  = "ghp_abcdef0123456789abcdef0123456789abcd";\n'
    )
    sigs = find_secrets(text)
    assert {s.pattern_name for s in sigs} == {"aws_access_key", "github_pat"}


def test_redact_keeps_first_4_and_last_2() -> None:
    assert redact("AKIAIOSFODNN7EXAMPLE") == "AKIA…LE"
    assert redact("short") == "…"
    assert redact("ab") == "…"


def test_secret_match_is_frozen() -> None:
    from dataclasses import FrozenInstanceError
    m = SecretMatch(
        pattern_name="x", severity="high", value="v", start=0,
    )
    with pytest.raises(FrozenInstanceError):
        m.value = "different"  # type: ignore[misc]
