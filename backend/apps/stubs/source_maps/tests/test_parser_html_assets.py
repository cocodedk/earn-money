"""Tests for stub 1.14 HTML asset extractor.

Slice 1: ``parse_html_assets(html, base_url, max_assets)`` collects
same-origin JS/CSS asset URLs from script/link tags per spec
§"Candidate asset collection". Returns absolute URLs paired with a
deterministic ``asset_kind`` classification.
"""
from __future__ import annotations

import unittest

from ..parser import Asset, parse_html_assets


_BASE = "https://example.test"


class ParseHtmlAssetsTests(unittest.TestCase):
    """Behavioural coverage for the HTML asset extractor."""

    def test_extracts_script_src(self) -> None:
        html = '<html><body><script src="/static/app.js"></script></body></html>'
        assets = parse_html_assets(html, _BASE)
        assert assets == [
            Asset(url=f"{_BASE}/static/app.js", kind="javascript"),
        ]

    def test_extracts_link_stylesheet(self) -> None:
        html = (
            '<html><head>'
            '<link rel="stylesheet" href="/static/site.css">'
            '</head></html>'
        )
        assets = parse_html_assets(html, _BASE)
        assert assets == [Asset(url=f"{_BASE}/static/site.css", kind="css")]

    def test_extracts_link_preload_script(self) -> None:
        html = (
            '<html><head>'
            '<link rel="preload" as="script" href="/static/main.js">'
            '</head></html>'
        )
        assets = parse_html_assets(html, _BASE)
        assert assets == [Asset(url=f"{_BASE}/static/main.js", kind="javascript")]

    def test_extracts_link_modulepreload(self) -> None:
        html = (
            '<html><head>'
            '<link rel="modulepreload" href="/static/mod.mjs">'
            '</head></html>'
        )
        assets = parse_html_assets(html, _BASE)
        assert assets == [Asset(url=f"{_BASE}/static/mod.mjs", kind="javascript")]

    def test_ignores_link_preload_when_not_as_script(self) -> None:
        html = (
            '<html><head>'
            '<link rel="preload" as="image" href="/static/hero.png">'
            '</head></html>'
        )
        # `as="image"` is not a JS/CSS asset — must be dropped so we
        # don't try to fetch arbitrary image URLs looking for source
        # maps.
        assert parse_html_assets(html, _BASE) == []

    def test_resolves_relative_url(self) -> None:
        html = '<script src="app.js"></script>'
        assets = parse_html_assets(html, f"{_BASE}/static/")
        assert assets == [Asset(url=f"{_BASE}/static/app.js", kind="javascript")]

    def test_drops_cross_origin(self) -> None:
        html = '<script src="https://cdn.other.test/lib.js"></script>'
        # Spec §Detection: candidate must be same-origin with base_url
        # unless global scope allows. Default policy = same-origin only.
        assert parse_html_assets(html, _BASE) == []

    def test_drops_non_http_schemes(self) -> None:
        html = (
            '<script src="data:application/javascript,console.log()"></script>'
            '<script src="javascript:void(0)"></script>'
            '<script src="blob:https://example.test/abc"></script>'
            '<script src="mailto:x@y.test"></script>'
        )
        assert parse_html_assets(html, _BASE) == []

    def test_drops_empty_src_and_href(self) -> None:
        html = (
            '<script src=""></script>'
            '<script></script>'
            '<link rel="stylesheet" href="">'
            '<link rel="stylesheet">'
        )
        assert parse_html_assets(html, _BASE) == []

    def test_dedupes_repeated_urls(self) -> None:
        html = (
            '<script src="/a.js"></script>'
            '<script src="/a.js"></script>'
            '<link rel="modulepreload" href="/a.js">'
        )
        assets = parse_html_assets(html, _BASE)
        # Same final URL collapses to one entry; the first kind wins
        # so the per-asset cache key downstream stays stable.
        assert assets == [Asset(url=f"{_BASE}/a.js", kind="javascript")]

    def test_preserves_document_order(self) -> None:
        html = (
            '<link rel="stylesheet" href="/c.css">'
            '<script src="/b.js"></script>'
            '<link rel="modulepreload" href="/a.mjs">'
        )
        urls = [a.url for a in parse_html_assets(html, _BASE)]
        assert urls == [f"{_BASE}/c.css", f"{_BASE}/b.js", f"{_BASE}/a.mjs"]

    def test_respects_max_assets_cap(self) -> None:
        # 60 script tags — extractor must trim to max_assets=50.
        scripts = "".join(f'<script src="/s{i}.js"></script>' for i in range(60))
        assets = parse_html_assets(scripts, _BASE, max_assets=50)
        assert len(assets) == 50

    def test_empty_html_returns_empty_list(self) -> None:
        assert parse_html_assets("", _BASE) == []

    def test_handles_malformed_html(self) -> None:
        # Unclosed tag / busted nesting still produces best-effort
        # extraction; never raises.
        html = '<script src="/x.js"<<<<<garbage'
        assets = parse_html_assets(html, _BASE)
        # html.parser is forgiving — the `src` attribute is still
        # recoverable. The contract is "never raises", not "perfect".
        assert all(a.url.startswith(_BASE) for a in assets)

    def test_classifies_kind_by_path_when_link_ambiguous(self) -> None:
        # `<link rel="preload" as="script">` always gets the script
        # kind regardless of extension — the rel/as combo wins over
        # the path suffix.
        html = (
            '<link rel="preload" as="script" href="/weird-suffix.dat">'
        )
        assets = parse_html_assets(html, _BASE)
        assert assets == [Asset(url=f"{_BASE}/weird-suffix.dat", kind="javascript")]

    def test_link_rel_case_insensitive(self) -> None:
        # HTML attribute values for rel are case-insensitive.
        html = '<link rel="STYLESHEET" href="/style.css">'
        assets = parse_html_assets(html, _BASE)
        assert assets == [Asset(url=f"{_BASE}/style.css", kind="css")]
