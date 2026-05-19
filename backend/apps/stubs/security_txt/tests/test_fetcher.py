"""Tests for stub 1.13 fetch_security_txt — single GET per candidate
path with cross-host redirect rejection.
"""
from __future__ import annotations

import unittest

import httpx

from ..fetcher import FetcherConfig, fetch_security_txt
from ._helpers import mocked_fetcher, resp


_BASE = "https://x.example"


class OkTests(unittest.TestCase):
    def test_200_with_body_returns_ok(self) -> None:
        url = f"{_BASE}/.well-known/security.txt"
        with mocked_fetcher({
            "/.well-known/security.txt": resp(
                "Contact: mailto:s@x.example\n", status_code=200, url=url,
            ),
        }):
            outcome = fetch_security_txt(_BASE, "/.well-known/security.txt")
        assert outcome.kind == "ok"
        assert outcome.status == 200
        assert outcome.body.startswith("Contact:")
        assert outcome.final_url == url


class AbsentTests(unittest.TestCase):
    def test_404_yields_absent(self) -> None:
        with mocked_fetcher({
            "/.well-known/security.txt": resp("", status_code=404),
        }):
            outcome = fetch_security_txt(_BASE, "/.well-known/security.txt")
        assert outcome.kind == "absent"
        assert outcome.status == 404

    def test_410_yields_absent(self) -> None:
        with mocked_fetcher({
            "/.well-known/security.txt": resp("", status_code=410),
        }):
            outcome = fetch_security_txt(_BASE, "/.well-known/security.txt")
        assert outcome.kind == "absent"

    def test_204_yields_absent(self) -> None:
        with mocked_fetcher({
            "/.well-known/security.txt": resp("", status_code=204),
        }):
            outcome = fetch_security_txt(_BASE, "/.well-known/security.txt")
        assert outcome.kind == "absent"

    def test_200_with_empty_body_yields_absent(self) -> None:
        # Spec §"absent when... body is empty after trimming".
        with mocked_fetcher({
            "/.well-known/security.txt": resp("   \n", status_code=200),
        }):
            outcome = fetch_security_txt(_BASE, "/.well-known/security.txt")
        assert outcome.kind == "absent"


class BlockedTests(unittest.TestCase):
    def test_401_yields_blocked(self) -> None:
        with mocked_fetcher({
            "/.well-known/security.txt": resp("denied", status_code=401),
        }):
            outcome = fetch_security_txt(_BASE, "/.well-known/security.txt")
        assert outcome.kind == "blocked"
        assert outcome.status == 401

    def test_403_yields_blocked(self) -> None:
        with mocked_fetcher({
            "/.well-known/security.txt": resp("forbidden", status_code=403),
        }):
            outcome = fetch_security_txt(_BASE, "/.well-known/security.txt")
        assert outcome.kind == "blocked"


class InconclusiveTests(unittest.TestCase):
    def test_5xx_yields_inconclusive(self) -> None:
        with mocked_fetcher({
            "/.well-known/security.txt": resp("err", status_code=503),
        }):
            outcome = fetch_security_txt(_BASE, "/.well-known/security.txt")
        assert outcome.kind == "inconclusive"

    def test_transport_error_yields_inconclusive(self) -> None:
        def raise_(_url, **_kwargs):
            raise httpx.ConnectError("DNS timeout")
        with mocked_fetcher(get_side_effect=raise_):
            outcome = fetch_security_txt(_BASE, "/.well-known/security.txt")
        assert outcome.kind == "inconclusive"
        assert outcome.status is None


class CrossHostRedirectTests(unittest.TestCase):
    def test_redirect_to_other_host_rejected_as_inconclusive(self) -> None:
        # The mocked client returns a response whose final_url is on
        # a different host — the fetcher must refuse to trust it.
        with mocked_fetcher({
            "/.well-known/security.txt": resp(
                "Contact: mailto:s@x.example\n",
                status_code=200,
                url="https://attacker.example/.well-known/security.txt",
            ),
        }):
            outcome = fetch_security_txt(_BASE, "/.well-known/security.txt")
        assert outcome.kind == "inconclusive"


class TruncationTests(unittest.TestCase):
    def test_body_capped_at_max(self) -> None:
        body = "Contact: mailto:s@x.example\n" + "x" * 10000
        with mocked_fetcher({
            "/.well-known/security.txt": resp(body, status_code=200),
        }):
            outcome = fetch_security_txt(
                _BASE, "/.well-known/security.txt",
                config=FetcherConfig(max_body_bytes=200),
            )
        assert len(outcome.body) == 200


class HeadersTests(unittest.TestCase):
    def test_request_uses_accept_text_plain(self) -> None:
        # Spec §Request discipline: Accept: text/plain.
        with mocked_fetcher({
            "/.well-known/security.txt": resp(
                "Contact: mailto:s@x.example\n", status_code=200,
            ),
        }) as client:
            fetch_security_txt(_BASE, "/.well-known/security.txt")
        # The client mock records every .get(url, headers=...) call.
        # Get the first call's kwargs to confirm Accept is set.
        assert client.get.call_args.kwargs["headers"]["Accept"].startswith(
            "text/plain"
        )


class ConfigValidationTests(unittest.TestCase):
    def test_negative_max_body_bytes_rejected(self) -> None:
        with self.assertRaises(ValueError):
            FetcherConfig(max_body_bytes=-1)
