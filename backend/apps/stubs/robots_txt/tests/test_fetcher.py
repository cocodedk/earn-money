"""Tests for stub 1.11 fetch_robots — single GET + manual same-origin
redirect handling.
"""
from __future__ import annotations

import unittest

import httpx

from ..fetcher import FetcherConfig, fetch_robots
from ._helpers import mocked_fetcher, resp


class HappyPathTests(unittest.TestCase):
    def test_200_returns_ok_with_body(self) -> None:
        with mocked_fetcher({
            "/robots.txt": resp(
                "User-agent: *\nDisallow: /admin", status_code=200,
            ),
        }):
            outcome = fetch_robots("https://example.com")

        assert outcome.kind == "ok"
        assert outcome.status == 200
        assert outcome.body.startswith("User-agent:")
        assert outcome.redirected is False
        assert outcome.final_url.endswith("/robots.txt")

    def test_204_returns_ok_empty_body(self) -> None:
        with mocked_fetcher({
            "/robots.txt": resp("", status_code=204),
        }):
            outcome = fetch_robots("https://example.com")

        assert outcome.kind == "ok"
        assert outcome.status == 204
        assert outcome.body == ""


class TruncationTests(unittest.TestCase):
    def test_body_truncated_to_max_bytes(self) -> None:
        long_body = "x" * 10000
        with mocked_fetcher({
            "/robots.txt": resp(long_body, status_code=200),
        }):
            outcome = fetch_robots(
                "https://example.com",
                config=FetcherConfig(max_body_bytes=256),
            )
        assert len(outcome.body) == 256


class StatusPassthroughTests(unittest.TestCase):
    def test_404_returns_ok_kind_with_status(self) -> None:
        # 404 is NOT an "unreachable" — the server replied. Classifier
        # handles the not_found mapping; the fetcher's job is to
        # surface the status faithfully.
        with mocked_fetcher({
            "/robots.txt": resp("not found", status_code=404),
        }):
            outcome = fetch_robots("https://example.com")
        assert outcome.kind == "ok"
        assert outcome.status == 404


class TransportErrorTests(unittest.TestCase):
    def test_connect_error_returns_unreachable(self) -> None:
        def raise_(_url, **_kwargs):
            raise httpx.ConnectError("DNS timeout")
        with mocked_fetcher(get_side_effect=raise_):
            outcome = fetch_robots("https://example.com")
        assert outcome.kind == "unreachable"
        assert outcome.status is None
        assert outcome.body == ""


class SameOriginRedirectTests(unittest.TestCase):
    def test_same_origin_redirect_followed(self) -> None:
        responses = {
            "/robots.txt": resp(
                "", status_code=302,
                headers={"Location": "/static/robots.txt"},
            ),
            "/static/robots.txt": resp(
                "User-agent: *\nDisallow: /admin", status_code=200,
            ),
        }
        with mocked_fetcher(responses):
            outcome = fetch_robots("https://example.com")

        assert outcome.kind == "ok"
        assert outcome.status == 200
        assert outcome.redirected is True
        assert "static/robots.txt" in outcome.final_url
        assert outcome.body.startswith("User-agent:")


class CrossOriginRedirectTests(unittest.TestCase):
    def test_cross_origin_redirect_blocked(self) -> None:
        with mocked_fetcher({
            "/robots.txt": resp(
                "", status_code=302,
                headers={"Location": "https://attacker.example/x"},
            ),
        }):
            outcome = fetch_robots("https://example.com")

        assert outcome.kind == "cross_origin_blocked"
        assert outcome.body == ""

    def test_absolute_same_origin_redirect_followed(self) -> None:
        responses = {
            "/robots.txt": resp(
                "", status_code=302,
                headers={
                    "Location": "https://example.com/static/robots.txt",
                },
            ),
            "/static/robots.txt": resp(
                "User-agent: *", status_code=200,
            ),
        }
        with mocked_fetcher(responses):
            outcome = fetch_robots("https://example.com")
        assert outcome.kind == "ok"
        assert outcome.redirected is True


class RedirectLimitTests(unittest.TestCase):
    def test_redirect_chain_within_limit_followed(self) -> None:
        # default max_redirects = 2 → two hops are allowed.
        responses = {
            "/robots.txt": resp(
                "", status_code=302, headers={"Location": "/r1"},
            ),
            "/r1": resp(
                "", status_code=302, headers={"Location": "/r2"},
            ),
            "/r2": resp("User-agent: *", status_code=200),
        }
        with mocked_fetcher(responses):
            outcome = fetch_robots("https://example.com")
        assert outcome.kind == "ok"
        assert outcome.redirected is True

    def test_redirect_chain_exceeds_limit_yields_redirect_limit(self) -> None:
        responses = {
            "/robots.txt": resp(
                "", status_code=302, headers={"Location": "/r1"},
            ),
            "/r1": resp(
                "", status_code=302, headers={"Location": "/r2"},
            ),
            "/r2": resp(
                "", status_code=302, headers={"Location": "/r3"},
            ),
        }
        with mocked_fetcher(responses):
            outcome = fetch_robots(
                "https://example.com",
                config=FetcherConfig(max_redirects=2),
            )
        assert outcome.kind == "redirect_limit"


class RedirectWithoutLocationTests(unittest.TestCase):
    def test_3xx_without_location_treated_as_ok_status(self) -> None:
        # A 302 without a Location header is malformed — return as
        # an `ok` outcome with the status so the classifier can
        # decide. The fetcher never invents a redirect target.
        with mocked_fetcher({
            "/robots.txt": resp("", status_code=302, headers={}),
        }):
            outcome = fetch_robots("https://example.com")
        assert outcome.kind == "ok"
        assert outcome.status == 302


class ConfigValidationTests(unittest.TestCase):
    def test_negative_max_redirects_rejected(self) -> None:
        with self.assertRaises(ValueError):
            FetcherConfig(max_redirects=-1)

    def test_negative_max_body_bytes_rejected(self) -> None:
        with self.assertRaises(ValueError):
            FetcherConfig(max_body_bytes=-1)
