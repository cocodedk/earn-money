"""Redaction contract for stub 1.2 server-headers.

Spec §Persistence → Evidence requirements: redact known
secret-bearing headers before persistence. The list:
Set-Cookie, Cookie, Authorization, Proxy-Authorization,
X-Api-Key, X-Auth-Token.

Redaction replaces the value with a fixed placeholder (preserving
the header presence as fingerprint evidence) — not deletion, since
the operator may need to know that an Authorization header WAS sent.
"""
from __future__ import annotations

import unittest

from ..redaction import REDACTED_VALUE, SENSITIVE_HEADERS, redact_headers


class SensitiveHeaderListTests(unittest.TestCase):
    def test_lowercased_canonical_set(self) -> None:
        for name in SENSITIVE_HEADERS:
            assert name == name.lower(), f"{name!r} should be lowercase"

    def test_includes_spec_minimum(self) -> None:
        required = {
            "set-cookie",
            "cookie",
            "authorization",
            "proxy-authorization",
            "x-api-key",
            "x-auth-token",
        }
        assert required <= SENSITIVE_HEADERS


class RedactHeadersTests(unittest.TestCase):
    def test_redacts_sensitive_value_keeps_key(self) -> None:
        out = redact_headers(
            {"Authorization": "Bearer abc.def.ghi", "Server": "nginx"}
        )
        assert out["Authorization"] == REDACTED_VALUE
        assert out["Server"] == "nginx"

    def test_redaction_is_case_insensitive_for_header_names(self) -> None:
        out = redact_headers({"SET-COOKIE": "session=xyz"})
        assert out["SET-COOKIE"] == REDACTED_VALUE

    def test_preserves_original_header_name_casing(self) -> None:
        out = redact_headers({"X-Api-Key": "secret-token"})
        # The KEY casing is preserved (so evidence still shows the
        # header was sent in that form); only the VALUE is masked.
        assert "X-Api-Key" in out
        assert out["X-Api-Key"] == REDACTED_VALUE

    def test_non_sensitive_pass_through(self) -> None:
        out = redact_headers(
            {"Server": "nginx/1.24.0", "X-Powered-By": "Express"}
        )
        assert out == {"Server": "nginx/1.24.0", "X-Powered-By": "Express"}

    def test_empty_input_returns_empty_dict(self) -> None:
        assert redact_headers({}) == {}

    def test_redaction_returns_a_new_dict(self) -> None:
        original = {"Authorization": "Bearer xyz"}
        out = redact_headers(original)
        assert out is not original
        assert original["Authorization"] == "Bearer xyz"
