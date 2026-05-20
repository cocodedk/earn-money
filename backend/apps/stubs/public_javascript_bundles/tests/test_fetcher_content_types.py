"""Tests for stub 1.15 fetch_bundle — content-type classification.

Spec §"Fetch bundle metadata" — accept the JavaScript content-type
allowlist (application/javascript, text/javascript, application/x-
javascript, text/ecmascript, application/ecmascript). Reject HTML
error pages, JSON APIs, images, fonts, and CSS. When the content
type is missing/generic and the URL strongly indicates JavaScript
and the body starts like JavaScript, accept anyway.
"""
from __future__ import annotations

import unittest

from ..fetcher import fetch_bundle
from ._helpers import mocked_fetcher, resp


_HOST = "https://example.test"


def _ok(url: str, body: str, ct: str = ""):
    headers = {"content-type": ct} if ct else {}
    return resp(body, status_code=200, url=url, headers=headers)


class AcceptedContentTypesTests(unittest.TestCase):
    def test_application_javascript_is_ok(self) -> None:
        url = f"{_HOST}/app.js"
        with mocked_fetcher({"/app.js": _ok(url, "x", "application/javascript")}):
            outcome = fetch_bundle(url)
        assert outcome.kind == "ok"
        assert outcome.status == 200

    def test_text_javascript_is_ok(self) -> None:
        url = f"{_HOST}/app.js"
        with mocked_fetcher({"/app.js": _ok(url, "x", "text/javascript")}):
            outcome = fetch_bundle(url)
        assert outcome.kind == "ok"

    def test_application_x_javascript_is_ok(self) -> None:
        url = f"{_HOST}/app.js"
        with mocked_fetcher({"/app.js": _ok(url, "x", "application/x-javascript")}):
            outcome = fetch_bundle(url)
        assert outcome.kind == "ok"

    def test_text_ecmascript_is_ok(self) -> None:
        url = f"{_HOST}/app.js"
        with mocked_fetcher({"/app.js": _ok(url, "x", "text/ecmascript")}):
            outcome = fetch_bundle(url)
        assert outcome.kind == "ok"

    def test_application_ecmascript_is_ok(self) -> None:
        url = f"{_HOST}/app.js"
        with mocked_fetcher({"/app.js": _ok(url, "x", "application/ecmascript")}):
            outcome = fetch_bundle(url)
        assert outcome.kind == "ok"

    def test_content_type_parameters_are_stripped(self) -> None:
        # Real servers send `application/javascript; charset=utf-8` —
        # the allowlist match must ignore parameters and case.
        url = f"{_HOST}/app.js"
        ct = "Application/JavaScript; charset=UTF-8"
        with mocked_fetcher({"/app.js": _ok(url, "x", ct)}):
            outcome = fetch_bundle(url)
        assert outcome.kind == "ok"


class RejectedContentTypesTests(unittest.TestCase):
    def test_text_html_yields_non_js(self) -> None:
        url = f"{_HOST}/app.js"
        with mocked_fetcher({"/app.js": _ok(url, "<html>", "text/html")}):
            outcome = fetch_bundle(url)
        assert outcome.kind == "non_js"
        assert outcome.status == 200
        assert outcome.body == "<html>"  # bounded excerpt for audit

    def test_application_json_yields_non_js(self) -> None:
        url = f"{_HOST}/data.js"
        with mocked_fetcher({"/data.js": _ok(url, "{}", "application/json")}):
            outcome = fetch_bundle(url)
        assert outcome.kind == "non_js"

    def test_image_png_yields_non_js(self) -> None:
        url = f"{_HOST}/asset.js"
        with mocked_fetcher({"/asset.js": _ok(url, "\x89PNG", "image/png")}):
            outcome = fetch_bundle(url)
        assert outcome.kind == "non_js"

    def test_text_css_yields_non_js(self) -> None:
        url = f"{_HOST}/styles.js"
        with mocked_fetcher({"/styles.js": _ok(url, ".x{}", "text/css")}):
            outcome = fetch_bundle(url)
        assert outcome.kind == "non_js"

    def test_font_woff_yields_non_js(self) -> None:
        url = f"{_HOST}/font.js"
        with mocked_fetcher({"/font.js": _ok(url, "wOFF", "font/woff2")}):
            outcome = fetch_bundle(url)
        assert outcome.kind == "non_js"


class GenericContentTypeHeuristicTests(unittest.TestCase):
    """Per spec: missing or generic content type is accepted when the
    URL path strongly indicates JavaScript AND the body starts like
    JavaScript."""

    def test_missing_ct_with_js_url_and_js_body_is_ok(self) -> None:
        url = f"{_HOST}/build.js"
        with mocked_fetcher({"/build.js": _ok(url, "function foo(){}")}):
            outcome = fetch_bundle(url)
        assert outcome.kind == "ok"

    def test_missing_ct_with_js_url_but_html_body_is_non_js(self) -> None:
        # 200 with no CT but body is HTML — error page masquerading
        # as a JS file.
        url = f"{_HOST}/missing.js"
        with mocked_fetcher({"/missing.js": _ok(url, "<!doctype html><html>")}):
            outcome = fetch_bundle(url)
        assert outcome.kind == "non_js"

    def test_missing_ct_with_non_js_url_is_non_js(self) -> None:
        # Even a perfectly JS-looking body shouldn't get accepted when
        # the URL gives no JS signal — keeps the heuristic conservative.
        url = f"{_HOST}/asset.bin"
        with mocked_fetcher({"/asset.bin": _ok(url, "function foo(){}")}):
            outcome = fetch_bundle(url)
        assert outcome.kind == "non_js"

    def test_octet_stream_with_js_url_and_js_body_is_ok(self) -> None:
        url = f"{_HOST}/chunk.mjs"
        with mocked_fetcher({"/chunk.mjs": _ok(
            url, "/* bundle */ export default 1;", "application/octet-stream",
        )}):
            outcome = fetch_bundle(url)
        assert outcome.kind == "ok"

    def test_text_plain_with_js_url_and_js_body_is_ok(self) -> None:
        url = f"{_HOST}/main.cjs"
        with mocked_fetcher({"/main.cjs": _ok(
            url, "// minified\n!function(){}();", "text/plain",
        )}):
            outcome = fetch_bundle(url)
        assert outcome.kind == "ok"

    def test_empty_body_with_js_url_and_generic_ct_is_non_js(self) -> None:
        # 200 with no body — a JS-looking URL alone is not enough; the
        # heuristic requires both URL and body signal.
        url = f"{_HOST}/empty.js"
        with mocked_fetcher({"/empty.js": _ok(url, "   \n", "")}):
            outcome = fetch_bundle(url)
        assert outcome.kind == "non_js"
