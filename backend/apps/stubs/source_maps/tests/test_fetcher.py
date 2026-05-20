"""Tests for stub 1.14 unified URL fetcher.

`fetch_url(url, base_origin, config)` performs a single GET and
classifies the response per spec §"Source map fetch":

* 200 → ok
* 401 / 403 → blocked
* 404 / 410 → absent
* TLS / DNS / timeout / TooManyRedirects → inconclusive
* cross-origin final URL after redirect → inconclusive

The same shape is used by the runner for HTML, JS/CSS asset, and
`.map` fetches — the per-call body cap and content-type capture
let the runner decide what to do downstream.
"""
from __future__ import annotations

import unittest

import httpx

from ..fetcher import FetcherConfig, FetchOutcome, fetch_url
from ._helpers import mocked_fetcher, resp


_BASE = "https://example.test"


class OkPathTests(unittest.TestCase):
    def test_200_with_body_returns_ok(self) -> None:
        url = f"{_BASE}/static/app.js"
        with mocked_fetcher({
            "/static/app.js": resp(
                "console.log(1);", status_code=200, url=url,
                headers={"content-type": "application/javascript"},
            ),
        }):
            outcome = fetch_url(url, _BASE)
        assert outcome.kind == "ok"
        assert outcome.status == 200
        assert outcome.body == "console.log(1);"
        assert outcome.final_url == url
        assert outcome.content_type == "application/javascript"

    def test_200_with_empty_body_still_ok(self) -> None:
        # The runner needs to distinguish "200 empty" from "404" so
        # an asset with the trivial body of `''` shouldn't get
        # demoted to absent. The downstream extractor returns None
        # for an empty body anyway.
        url = f"{_BASE}/empty.js"
        with mocked_fetcher({"/empty.js": resp("", status_code=200, url=url)}):
            outcome = fetch_url(url, _BASE)
        assert outcome.kind == "ok"
        assert outcome.body == ""


class AbsentTests(unittest.TestCase):
    def test_404_yields_absent(self) -> None:
        url = f"{_BASE}/missing.js"
        with mocked_fetcher({"/missing.js": resp("", status_code=404, url=url)}):
            outcome = fetch_url(url, _BASE)
        assert outcome.kind == "absent"
        assert outcome.status == 404

    def test_410_yields_absent(self) -> None:
        url = f"{_BASE}/gone.js"
        with mocked_fetcher({"/gone.js": resp("", status_code=410, url=url)}):
            outcome = fetch_url(url, _BASE)
        assert outcome.kind == "absent"


class BlockedTests(unittest.TestCase):
    def test_401_yields_blocked(self) -> None:
        url = f"{_BASE}/protected.js.map"
        with mocked_fetcher({
            "/protected.js.map": resp("", status_code=401, url=url),
        }):
            outcome = fetch_url(url, _BASE)
        assert outcome.kind == "blocked"
        assert outcome.status == 401

    def test_blocked_response_preserves_body_for_audit(self) -> None:
        # Spec §Persistence line 303: "blocked or oversized source
        # map response when useful for audit" — the runner needs the
        # bounded body so a 403'd map can land as Evidence with a
        # raw_excerpt explaining what the server returned.
        url = f"{_BASE}/protected.js.map"
        with mocked_fetcher({
            "/protected.js.map": resp(
                "<html>Forbidden</html>", status_code=403, url=url,
            ),
        }):
            outcome = fetch_url(url, _BASE)
        assert outcome.kind == "blocked"
        assert outcome.body == "<html>Forbidden</html>"

    def test_403_yields_blocked(self) -> None:
        url = f"{_BASE}/protected.js.map"
        with mocked_fetcher({
            "/protected.js.map": resp("", status_code=403, url=url),
        }):
            outcome = fetch_url(url, _BASE)
        assert outcome.kind == "blocked"


class InconclusiveTests(unittest.TestCase):
    def test_transport_error_yields_inconclusive(self) -> None:
        # TLS / DNS / connect failures all surface as TransportError.
        def boom(*_args, **_kwargs):
            raise httpx.ConnectError("dns boom")
        with mocked_fetcher(get_side_effect=boom):
            outcome = fetch_url(f"{_BASE}/x.js.map", _BASE)
        assert outcome.kind == "inconclusive"
        assert outcome.status is None

    def test_too_many_redirects_yields_inconclusive(self) -> None:
        # httpx.TooManyRedirects is NOT a TransportError subclass;
        # capped at max_redirects=3 means real servers with deep
        # redirect chains can hit this path. The fetcher must
        # catch it explicitly.
        def loop(*_args, **_kwargs):
            raise httpx.TooManyRedirects(
                "too many",
                request=httpx.Request("GET", f"{_BASE}/x.js.map"),
            )
        with mocked_fetcher(get_side_effect=loop):
            outcome = fetch_url(f"{_BASE}/x.js.map", _BASE)
        assert outcome.kind == "inconclusive"

    def test_cross_origin_final_url_yields_inconclusive(self) -> None:
        # If the server redirects to a different origin we MUST NOT
        # treat the body as evidence — the spec demands same-origin
        # final URL.
        cross = "https://cdn.other.test/static/app.js.map"
        url = f"{_BASE}/static/app.js.map"
        with mocked_fetcher({"/static/app.js.map": resp(
            "{}", status_code=200, url=cross,
        )}):
            outcome = fetch_url(url, _BASE)
        assert outcome.kind == "inconclusive"
        assert outcome.final_url == cross

    def test_unexpected_status_500_yields_inconclusive(self) -> None:
        # Spec doesn't pin 5xx to a kind; the fetcher defaults to
        # inconclusive so the runner can audit transient errors
        # without minting a false positive.
        url = f"{_BASE}/maybe.js.map"
        with mocked_fetcher({"/maybe.js.map": resp(
            "", status_code=503, url=url,
        )}):
            outcome = fetch_url(url, _BASE)
        assert outcome.kind == "inconclusive"
        assert outcome.status == 503


class BodyCapTests(unittest.TestCase):
    def test_body_capped_at_max_response_bytes(self) -> None:
        # A 3-MB body is way over the 2-MB default cap; the
        # fetcher must trim to keep memory bounded.
        url = f"{_BASE}/huge.js"
        big_body = "x" * (3 * 1024 * 1024)
        with mocked_fetcher({"/huge.js": resp(
            big_body, status_code=200, url=url,
        )}):
            outcome = fetch_url(url, _BASE)
        assert len(outcome.body) <= 2_000_000
        assert outcome.kind == "ok"

    def test_custom_max_body_bytes_honoured(self) -> None:
        url = f"{_BASE}/small.js"
        with mocked_fetcher({"/small.js": resp(
            "a" * 1000, status_code=200, url=url,
        )}):
            outcome = fetch_url(
                url, _BASE, config=FetcherConfig(max_body_bytes=100),
            )
        assert len(outcome.body) == 100


class ContentTypeTests(unittest.TestCase):
    def test_missing_content_type_returns_empty_string(self) -> None:
        url = f"{_BASE}/no-type"
        with mocked_fetcher({"/no-type": resp(
            "{}", status_code=200, url=url,
        )}):
            outcome = fetch_url(url, _BASE)
        assert outcome.content_type == ""

    def test_returns_dataclass_type(self) -> None:
        url = f"{_BASE}/x"
        with mocked_fetcher({"/x": resp("y", status_code=200, url=url)}):
            outcome = fetch_url(url, _BASE)
        assert isinstance(outcome, FetchOutcome)


class TestHelperFallbackTests(unittest.TestCase):
    """The mock falls back to 404 for unmocked URLs so a test that
    forgets to stub a probe surfaces it loudly via `kind="absent"`
    rather than a confusing pass on stale state."""

    def test_unmocked_url_returns_404_through_helper(self) -> None:
        with mocked_fetcher({"/other.js": resp("y", status_code=200)}):
            outcome = fetch_url(f"{_BASE}/never-stubbed.js", _BASE)
        assert outcome.kind == "absent"
        assert outcome.status == 404
