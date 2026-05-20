"""Tests for stub 1.15 fetch_bundle — HTTP status classification.

Spec §"Fetch bundle metadata" + §"Status rules":
* 200 → ok / non_js (content-type decides; covered by content-type tests)
* 404 / 410 → absent (asset missing or gone)
* 401 / 403 → blocked
* 5xx and unexpected → inconclusive
"""
from __future__ import annotations

import unittest

import httpx

from ..fetcher import fetch_bundle
from ._helpers import mocked_fetcher, resp


_HOST = "https://example.test"


class AbsentTests(unittest.TestCase):
    def test_404_yields_absent(self) -> None:
        url = f"{_HOST}/missing.js"
        with mocked_fetcher({"/missing.js": resp("", status_code=404, url=url)}):
            outcome = fetch_bundle(url)
        assert outcome.kind == "absent"
        assert outcome.status == 404
        assert outcome.sha256 is None

    def test_410_yields_absent(self) -> None:
        url = f"{_HOST}/gone.js"
        with mocked_fetcher({"/gone.js": resp("", status_code=410, url=url)}):
            outcome = fetch_bundle(url)
        assert outcome.kind == "absent"


class BlockedTests(unittest.TestCase):
    def test_401_yields_blocked(self) -> None:
        url = f"{_HOST}/private.js"
        with mocked_fetcher({"/private.js": resp("", status_code=401, url=url)}):
            outcome = fetch_bundle(url)
        assert outcome.kind == "blocked"
        assert outcome.status == 401

    def test_403_yields_blocked(self) -> None:
        url = f"{_HOST}/forbidden.js"
        with mocked_fetcher({"/forbidden.js": resp(
            "<html>403</html>", status_code=403, url=url,
        )}):
            outcome = fetch_bundle(url)
        assert outcome.kind == "blocked"
        # Body retained on blocked for audit — same policy as source_maps.
        assert outcome.body == "<html>403</html>"


class InconclusiveTests(unittest.TestCase):
    def test_500_yields_inconclusive(self) -> None:
        url = f"{_HOST}/oops.js"
        with mocked_fetcher({"/oops.js": resp("", status_code=500, url=url)}):
            outcome = fetch_bundle(url)
        assert outcome.kind == "inconclusive"
        assert outcome.status == 500

    def test_503_yields_inconclusive(self) -> None:
        url = f"{_HOST}/down.js"
        with mocked_fetcher({"/down.js": resp("", status_code=503, url=url)}):
            outcome = fetch_bundle(url)
        assert outcome.kind == "inconclusive"

    def test_unexpected_3xx_yields_inconclusive(self) -> None:
        # httpx follows redirects internally, so a 3xx surfacing here
        # means an unexpected status code reached the classifier.
        url = f"{_HOST}/weird.js"
        with mocked_fetcher({"/weird.js": resp("", status_code=304, url=url)}):
            outcome = fetch_bundle(url)
        assert outcome.kind == "inconclusive"
        assert outcome.status == 304

    def test_transport_error_yields_inconclusive(self) -> None:
        def boom(*_args, **_kwargs):
            raise httpx.ConnectError("dns boom")
        with mocked_fetcher(get_side_effect=boom):
            outcome = fetch_bundle(f"{_HOST}/x.js")
        assert outcome.kind == "inconclusive"
        assert outcome.status is None
        assert outcome.sha256 is None
        assert outcome.body == ""

    def test_unmocked_url_returns_404_via_helper_fallback(self) -> None:
        # The mock returns 404 for any URL it didn't stub, so a test
        # that forgets to register a probe surfaces it loudly as
        # kind=absent rather than silently passing on stale state.
        with mocked_fetcher({"/known.js": resp("", status_code=200, url=f"{_HOST}/known.js")}):
            outcome = fetch_bundle(f"{_HOST}/never-mocked.js")
        assert outcome.kind == "absent"
        assert outcome.status == 404

    def test_too_many_redirects_yields_inconclusive(self) -> None:
        # TooManyRedirects is NOT a TransportError subclass — must
        # be caught explicitly. Spec §Safety: "must not retry
        # indefinitely after timeouts or TLS errors".
        def loop(*_args, **_kwargs):
            raise httpx.TooManyRedirects(
                "loop",
                request=httpx.Request("GET", f"{_HOST}/x.js"),
            )
        with mocked_fetcher(get_side_effect=loop):
            outcome = fetch_bundle(f"{_HOST}/x.js")
        assert outcome.kind == "inconclusive"
