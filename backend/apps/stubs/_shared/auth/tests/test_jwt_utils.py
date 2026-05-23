"""Tests for _shared/auth/jwt_utils.py — JWT decode, redact, fingerprint, build."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json

import pytest

from apps.stubs._shared.auth.jwt_utils import (
    ParsedJwt,
    build_alg_none_token,
    build_hs_token,
    fingerprint_token,
    parse_jwt,
    redact_token,
)


def _b64url(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _make_jwt(header: dict, payload: dict, sig: str = "fakesig") -> str:
    h = _b64url(json.dumps(header))
    p = _b64url(json.dumps(payload))
    return f"{h}.{p}.{sig}"


_VALID_TOKEN = _make_jwt(
    {"alg": "HS256", "typ": "JWT"},
    {"sub": "user1", "exp": 9999999999, "iat": 1700000000},
)

_NONE_TOKEN = _make_jwt(
    {"alg": "none", "typ": "JWT"},
    {"sub": "user1"},
    sig="",
)


class TestParseJwt:
    def test_parses_valid_token(self):
        result = parse_jwt(_VALID_TOKEN)
        assert result is not None
        assert result.header["alg"] == "HS256"
        assert result.payload["sub"] == "user1"
        assert result.payload["exp"] == 9999999999
        assert result.signature_present is True

    def test_parses_alg_none_no_signature(self):
        result = parse_jwt(_NONE_TOKEN)
        assert result is not None
        assert result.header["alg"] == "none"
        assert result.signature_present is False

    def test_returns_none_on_not_a_jwt(self):
        assert parse_jwt("notajwt") is None
        assert parse_jwt("") is None
        assert parse_jwt("a.b") is None

    def test_returns_none_on_invalid_base64(self):
        assert parse_jwt("!!!.!!!.!!!") is None

    def test_returns_none_on_invalid_json(self):
        bad = _b64url(b"not-json") + "." + _b64url(b"also-not-json") + ".sig"
        assert parse_jwt(bad) is None

    def test_missing_exp_is_none(self):
        token = _make_jwt({"alg": "HS256"}, {"sub": "x"})
        result = parse_jwt(token)
        assert result is not None
        assert result.payload.get("exp") is None

    def test_three_parts_required(self):
        assert parse_jwt("a.b.c.d") is None


class TestRedactToken:
    def test_long_token_truncated(self):
        result = redact_token("a" * 100)
        assert result.endswith("...")
        assert len(result) < 50

    def test_short_token_still_redacted(self):
        result = redact_token("abc")
        assert "..." in result

    def test_returns_string(self):
        assert isinstance(redact_token(_VALID_TOKEN), str)


class TestFingerprintToken:
    def test_fingerprint_is_hex_string(self):
        fp = fingerprint_token(_VALID_TOKEN)
        assert isinstance(fp, str)
        assert len(fp) == 16

    def test_same_token_same_fingerprint(self):
        assert fingerprint_token(_VALID_TOKEN) == fingerprint_token(_VALID_TOKEN)

    def test_different_tokens_different_fingerprint(self):
        t2 = _make_jwt({"alg": "RS256"}, {"sub": "user2"})
        assert fingerprint_token(_VALID_TOKEN) != fingerprint_token(t2)


class TestBuildAlgNoneToken:
    def test_produces_two_dots(self):
        token = build_alg_none_token({"alg": "HS256"}, {"sub": "x"})
        parts = token.split(".")
        assert len(parts) == 3
        assert parts[2] == ""

    def test_header_alg_is_none(self):
        token = build_alg_none_token({"alg": "HS256"}, {"sub": "x"})
        header_bytes = base64.urlsafe_b64decode(token.split(".")[0] + "==")
        header = json.loads(header_bytes)
        assert header["alg"] == "none"

    def test_payload_preserved(self):
        payload = {"sub": "alice", "exp": 9999}
        token = build_alg_none_token({"alg": "HS256"}, payload)
        part = token.split(".")[1]
        restored = json.loads(base64.urlsafe_b64decode(part + "=="))
        assert restored["sub"] == "alice"
        assert restored["exp"] == 9999


class TestBuildHsToken:
    def test_hs256_signature_verifiable(self):
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {"sub": "bob"}
        secret = b"test-secret"
        token = build_hs_token(header, payload, secret, "HS256")
        parts = token.split(".")
        assert len(parts) == 3
        signing_input = f"{parts[0]}.{parts[1]}".encode()
        expected_sig = base64.urlsafe_b64encode(
            hmac.new(secret, signing_input, "sha256").digest()
        ).rstrip(b"=").decode()
        assert parts[2] == expected_sig

    def test_hs384_uses_sha384(self):
        header = {"alg": "HS384"}
        payload = {"sub": "carol"}
        secret = b"s"
        token = build_hs_token(header, payload, secret, "HS384")
        parts = token.split(".")
        signing_input = f"{parts[0]}.{parts[1]}".encode()
        expected_sig = base64.urlsafe_b64encode(
            hmac.new(secret, signing_input, "sha384").digest()
        ).rstrip(b"=").decode()
        assert parts[2] == expected_sig

    def test_hs512_uses_sha512(self):
        header = {"alg": "HS512"}
        payload = {"sub": "dave"}
        secret = b"s"
        token = build_hs_token(header, payload, secret, "HS512")
        parts = token.split(".")
        signing_input = f"{parts[0]}.{parts[1]}".encode()
        expected_sig = base64.urlsafe_b64encode(
            hmac.new(secret, signing_input, "sha512").digest()
        ).rstrip(b"=").decode()
        assert parts[2] == expected_sig

    def test_unknown_alg_raises(self):
        with pytest.raises(ValueError, match="Unsupported"):
            build_hs_token({"alg": "RS256"}, {}, b"s", "RS256")
