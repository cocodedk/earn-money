"""Tests for stub 1.15 body-text extractors — API paths, public env
names, suspicious indicators.

Spec §4 'Public route/API hints', 'Public environment/config names',
'Suspicious but non-secret indicators'. Each extractor scans the
bundle body and returns deduplicated strings; redaction of token-
like values is a separate module (secret_redactors).
"""
from __future__ import annotations

import unittest

from ..body_text_extractors import (
    extract_api_path_hints,
    extract_public_env_names,
    extract_suspicious_indicators,
)


class ApiPathTests(unittest.TestCase):
    def test_api_prefix(self) -> None:
        body = 'fetch("/api/products").then(...)'
        assert "/api/products" in extract_api_path_hints(body)

    def test_graphql_path(self) -> None:
        body = "var ENDPOINT = '/graphql';"
        assert "/graphql" in extract_api_path_hints(body)

    def test_rest_prefix(self) -> None:
        assert "/rest/orders" in extract_api_path_hints(
            'fetch("/rest/orders")'
        )

    def test_v1_prefix(self) -> None:
        # The extractor captures the whole path token, not just the
        # version prefix — gives the operator the actionable URL.
        assert "/v1/users/me" in extract_api_path_hints(
            'axios.get("/v1/users/me")'
        )

    def test_v2_prefix(self) -> None:
        assert "/v2/items" in extract_api_path_hints('"/v2/items"')

    def test_nested_path_captured(self) -> None:
        body = 'fetch("/api/v1/admin/users")'
        # We don't try to guess depth — capture the full known
        # prefix + nested segments to give the operator something
        # actionable to triage.
        result = extract_api_path_hints(body)
        assert any(p.startswith("/api/") for p in result)

    def test_no_api_returns_empty(self) -> None:
        assert extract_api_path_hints("function foo(){}") == []

    def test_deduped(self) -> None:
        body = 'a("/api/products"); b("/api/products")'
        result = extract_api_path_hints(body)
        assert result.count("/api/products") == 1

    def test_partial_match_excluded(self) -> None:
        # `/apiary/...` must NOT match — the spec wants a strict
        # `/api/` prefix, not "starts with /api".
        assert extract_api_path_hints('"/apiary/users"') == []

    def test_order_preserved(self) -> None:
        # First-seen order helps the operator scan output linearly.
        body = 'a("/v2/x"); b("/api/products"); c("/graphql")'
        result = extract_api_path_hints(body)
        assert result == ["/v2/x", "/api/products", "/graphql"]


class PublicEnvNameTests(unittest.TestCase):
    def test_public_prefix(self) -> None:
        body = "var x = process.env.PUBLIC_API_URL;"
        assert "PUBLIC_API_URL" in extract_public_env_names(body)

    def test_next_public_prefix(self) -> None:
        body = "const u = process.env.NEXT_PUBLIC_API_URL;"
        assert "NEXT_PUBLIC_API_URL" in extract_public_env_names(body)

    def test_vite_prefix(self) -> None:
        body = "import.meta.env.VITE_API_BASE"
        assert "VITE_API_BASE" in extract_public_env_names(body)

    def test_react_app_prefix(self) -> None:
        body = "REACT_APP_TURNSTILE_KEY=key"
        assert "REACT_APP_TURNSTILE_KEY" in extract_public_env_names(body)

    def test_nuxt_public_prefix(self) -> None:
        body = "NUXT_PUBLIC_API_BASE=x"
        assert "NUXT_PUBLIC_API_BASE" in extract_public_env_names(body)

    def test_non_public_env_ignored(self) -> None:
        # Spec is explicit — only NAMES starting with the listed
        # public prefixes should be recorded. Generic env names
        # (DATABASE_URL, JWT_SECRET) carry secret-leak risk and
        # belong to the secret-redactor path, not this extractor.
        assert extract_public_env_names("DATABASE_URL=postgres://x") == []
        assert extract_public_env_names("JWT_SECRET=abc") == []

    def test_no_env_returns_empty(self) -> None:
        assert extract_public_env_names("function foo(){}") == []

    def test_deduped(self) -> None:
        body = "PUBLIC_A=1; PUBLIC_A=2"
        result = extract_public_env_names(body)
        assert result.count("PUBLIC_A") == 1

    def test_short_name_rejected(self) -> None:
        # The prefix alone (e.g. `PUBLIC_`) isn't a meaningful name;
        # require at least one trailing char to count as a variable.
        assert extract_public_env_names("PUBLIC_=x") == []


class SuspiciousIndicatorTests(unittest.TestCase):
    def test_localhost_detected(self) -> None:
        assert "localhost" in extract_suspicious_indicators(
            'var URL = "http://localhost:3000";'
        )

    def test_loopback_ipv4_detected(self) -> None:
        assert "127.0.0.1" in extract_suspicious_indicators(
            'fetch("http://127.0.0.1:8080")'
        )

    def test_private_10_range_detected(self) -> None:
        body = 'API = "http://10.0.5.42:8080/api"'
        result = extract_suspicious_indicators(body)
        assert any(i.startswith("10.") for i in result)

    def test_private_192_168_range_detected(self) -> None:
        body = 'host = "192.168.1.100"'
        result = extract_suspicious_indicators(body)
        assert "192.168.1.100" in result

    def test_private_172_range_detected(self) -> None:
        # 172.16.0.0/12 — covers 172.16.*.* through 172.31.*.*.
        body = 'host = "172.20.5.5"; host2 = "172.31.255.1"'
        result = extract_suspicious_indicators(body)
        assert "172.20.5.5" in result and "172.31.255.1" in result

    def test_172_outside_private_range_excluded(self) -> None:
        # 172.15.* and 172.32.* are PUBLIC. Must NOT flag.
        body = '"172.15.0.1"; "172.32.0.1"'
        assert extract_suspicious_indicators(body) == []

    def test_staging_host_detected(self) -> None:
        body = 'URL = "https://staging.example.com/api"'
        result = extract_suspicious_indicators(body)
        assert any("staging" in i.lower() for i in result)

    def test_dev_host_detected(self) -> None:
        body = 'URL = "https://dev.example.com/"'
        result = extract_suspicious_indicators(body)
        assert any("dev" in i.lower() for i in result)

    def test_no_indicators_returns_empty(self) -> None:
        body = 'URL = "https://api.example.com/v1"'
        assert extract_suspicious_indicators(body) == []

    def test_deduped(self) -> None:
        body = "localhost; localhost; localhost"
        assert extract_suspicious_indicators(body).count("localhost") == 1

    def test_0_0_0_0_detected(self) -> None:
        # All-zeros bind address — common dev/CI marker that leaks
        # into bundles via env interpolation.
        assert "0.0.0.0" in extract_suspicious_indicators(
            'BIND = "0.0.0.0:3000"'
        )
