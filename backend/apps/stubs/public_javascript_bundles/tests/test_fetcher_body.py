"""Tests for stub 1.15 fetch_bundle — body, hash, truncation, headers.

Spec §"Fetch bundle metadata":
* Read at most ``max_bundle_bytes``; mark ``truncated=true`` and
  still hash the bytes read when exceeded.
* Compute a stable content hash over the bytes read.
* Record response metadata (content-type, content-length, etag,
  last-modified, cache-control) for the persistence signature.
"""
from __future__ import annotations

import hashlib
import unittest

from ..fetcher import BundleFetcherConfig, BundleFetchOutcome, fetch_bundle
from ._helpers import mocked_fetcher, resp


def _resp_bytes(body_bytes: bytes, *, url: str, ct: str = "application/javascript"):
    """Build a 200 response from raw bytes — used to drive the
    fetcher's byte-semantic cap path without UTF-8 round-trip."""
    import httpx
    return httpx.Response(
        status_code=200,
        headers={"content-type": ct},
        content=body_bytes,
        request=httpx.Request("GET", url),
    )


_HOST = "https://example.test"


class Sha256Tests(unittest.TestCase):
    def test_sha256_is_hex_of_body_bytes(self) -> None:
        body = "function foo(){}"
        url = f"{_HOST}/app.js"
        with mocked_fetcher({"/app.js": resp(
            body, status_code=200, url=url,
            headers={"content-type": "application/javascript"},
        )}):
            outcome = fetch_bundle(url)
        expected = hashlib.sha256(body.encode("utf-8")).hexdigest()
        assert outcome.sha256 == expected
        assert outcome.bytes_read == len(body)

    def test_sha256_none_on_transport_failure(self) -> None:
        # Already covered by status tests; restated here so the
        # body-side contract is testable from one place.
        url = f"{_HOST}/missing.js"
        with mocked_fetcher({"/missing.js": resp("", status_code=404, url=url)}):
            outcome = fetch_bundle(url)
        assert outcome.sha256 is None


class TruncationTests(unittest.TestCase):
    def test_oversized_body_capped_and_marked_truncated(self) -> None:
        # 3 MiB body, cap at 1 MiB. The body in the outcome must
        # equal the cap and truncated must be True; the hash must
        # cover exactly the bytes read (not the full source).
        url = f"{_HOST}/huge.js"
        body = "a" * (3 * 1024 * 1024)
        with mocked_fetcher({"/huge.js": resp(
            body, status_code=200, url=url,
            headers={"content-type": "application/javascript"},
        )}):
            outcome = fetch_bundle(
                url, config=BundleFetcherConfig(max_body_bytes=1024 * 1024),
            )
        assert outcome.kind == "ok"
        assert outcome.bytes_read == 1024 * 1024
        assert outcome.truncated is True
        expected = hashlib.sha256(("a" * (1024 * 1024)).encode("utf-8")).hexdigest()
        assert outcome.sha256 == expected

    def test_truncation_is_byte_semantic_not_char_semantic(self) -> None:
        # Spec §"Fetch bundle metadata": max_bundle_bytes is a BYTE
        # budget. A 4-byte-per-char UTF-8 payload at 1024 chars is
        # 4096 bytes — must be truncated when the cap is 1024 bytes.
        # The previous str-slicing implementation would have let it
        # through silently.
        url = f"{_HOST}/utf8.js"
        char = "𝄞"  # U+1D11E G clef — 4 bytes in UTF-8
        body_bytes = (char * 1024).encode("utf-8")  # 4096 wire bytes
        assert len(body_bytes) == 4096
        with mocked_fetcher({"/utf8.js": _resp_bytes(body_bytes, url=url)}):
            outcome = fetch_bundle(
                url, config=BundleFetcherConfig(max_body_bytes=1024),
            )
        assert outcome.kind == "ok"
        assert outcome.bytes_read == 1024
        assert outcome.truncated is True
        # sha256 is over the bytes read, not the decoded chars.
        assert outcome.sha256 == hashlib.sha256(body_bytes[:1024]).hexdigest()

    def test_undersized_body_not_truncated(self) -> None:
        url = f"{_HOST}/small.js"
        with mocked_fetcher({"/small.js": resp(
            "x", status_code=200, url=url,
            headers={"content-type": "application/javascript"},
        )}):
            outcome = fetch_bundle(url)
        assert outcome.truncated is False
        assert outcome.bytes_read == 1


class HeaderCaptureTests(unittest.TestCase):
    def test_records_etag_last_modified_cache_control_and_content_length(self) -> None:
        url = f"{_HOST}/app.js"
        headers = {
            "content-type": "application/javascript",
            "content-length": "42",
            "etag": 'W/"abc123"',
            "last-modified": "Wed, 21 Oct 2026 07:28:00 GMT",
            "cache-control": "max-age=3600, public",
        }
        with mocked_fetcher({"/app.js": resp(
            "x", status_code=200, url=url, headers=headers,
        )}):
            outcome = fetch_bundle(url)
        assert outcome.content_type == "application/javascript"
        assert outcome.content_length == 42
        assert outcome.etag == 'W/"abc123"'
        assert outcome.last_modified == "Wed, 21 Oct 2026 07:28:00 GMT"
        assert outcome.cache_control == "max-age=3600, public"

    def test_missing_optional_headers_yield_none(self) -> None:
        # Note: httpx auto-injects content-length on response
        # construction, so missing-CL is exercised in
        # test_content_length_absent_yields_none below.
        url = f"{_HOST}/bare.js"
        with mocked_fetcher({"/bare.js": resp(
            "x", status_code=200, url=url,
            headers={"content-type": "application/javascript"},
        )}):
            outcome = fetch_bundle(url)
        assert outcome.etag is None
        assert outcome.last_modified is None
        assert outcome.cache_control is None

    def test_content_length_absent_yields_none(self) -> None:
        # The wire-level case: server omits content-length entirely
        # (chunked transfer or HEAD-then-GET pattern). Strip the
        # auto-injected header to reach the None branch in the parser.
        url = f"{_HOST}/chunked.js"
        response = resp(
            "x", status_code=200, url=url,
            headers={"content-type": "application/javascript"},
        )
        del response.headers["content-length"]
        with mocked_fetcher({"/chunked.js": response}):
            outcome = fetch_bundle(url)
        assert outcome.content_length is None

    def test_invalid_content_length_treated_as_none(self) -> None:
        # Malformed `content-length: abc` must not crash the fetcher.
        url = f"{_HOST}/bad.js"
        with mocked_fetcher({"/bad.js": resp(
            "x", status_code=200, url=url,
            headers={
                "content-type": "application/javascript",
                "content-length": "abc",
            },
        )}):
            outcome = fetch_bundle(url)
        assert outcome.content_length is None


class OutcomeShapeTests(unittest.TestCase):
    def test_returns_bundle_fetch_outcome_dataclass(self) -> None:
        url = f"{_HOST}/x.js"
        with mocked_fetcher({"/x.js": resp(
            "x", status_code=200, url=url,
            headers={"content-type": "application/javascript"},
        )}):
            outcome = fetch_bundle(url)
        assert isinstance(outcome, BundleFetchOutcome)
        assert outcome.final_url == url
