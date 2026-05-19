"""Pure-function tests for stub 1.12 sitemap.xml parser.

Spec §URL extraction: extract `<url><loc>` for urlset sitemaps and
`<sitemap><loc>` for sitemap indexes, with optional lastmod /
changefreq / priority on urlset entries.
"""
from __future__ import annotations

import unittest

from ..parser import parse_sitemap_xml


class UrlsetTests(unittest.TestCase):
    def test_simple_urlset_extracts_locs(self) -> None:
        body = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://x.example/a</loc></url>
          <url><loc>https://x.example/b</loc></url>
        </urlset>"""
        parsed = parse_sitemap_xml(body)
        assert parsed.kind == "urlset"
        locs = [e.loc for e in parsed.entries]
        assert locs == ["https://x.example/a", "https://x.example/b"]

    def test_url_with_meta_fields_extracted(self) -> None:
        body = """<urlset>
          <url>
            <loc>https://x.example/foo</loc>
            <lastmod>2026-05-19T12:00:00Z</lastmod>
            <changefreq>weekly</changefreq>
            <priority>0.8</priority>
          </url>
        </urlset>"""
        parsed = parse_sitemap_xml(body)
        entry = parsed.entries[0]
        assert entry.loc == "https://x.example/foo"
        assert entry.lastmod == "2026-05-19T12:00:00Z"
        assert entry.changefreq == "weekly"
        assert entry.priority == "0.8"

    def test_cdata_wrapped_loc_unwrapped(self) -> None:
        body = """<urlset>
          <url><loc><![CDATA[https://x.example/cdata-url]]></loc></url>
        </urlset>"""
        parsed = parse_sitemap_xml(body)
        assert parsed.entries[0].loc == "https://x.example/cdata-url"

    def test_relative_loc_preserved(self) -> None:
        body = """<urlset>
          <url><loc>/relative-path</loc></url>
        </urlset>"""
        parsed = parse_sitemap_xml(body)
        assert parsed.entries[0].loc == "/relative-path"


class SitemapIndexTests(unittest.TestCase):
    def test_sitemap_index_kind_detected(self) -> None:
        body = """<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <sitemap><loc>https://x.example/sitemap-1.xml</loc></sitemap>
          <sitemap><loc>https://x.example/sitemap-2.xml</loc></sitemap>
        </sitemapindex>"""
        parsed = parse_sitemap_xml(body)
        assert parsed.kind == "sitemapindex"
        locs = [e.loc for e in parsed.entries]
        assert locs == [
            "https://x.example/sitemap-1.xml",
            "https://x.example/sitemap-2.xml",
        ]

    def test_sitemap_index_lastmod_extracted(self) -> None:
        body = """<sitemapindex>
          <sitemap>
            <loc>https://x.example/sitemap-1.xml</loc>
            <lastmod>2026-05-19</lastmod>
          </sitemap>
        </sitemapindex>"""
        parsed = parse_sitemap_xml(body)
        assert parsed.entries[0].lastmod == "2026-05-19"


class DeduplicationTests(unittest.TestCase):
    def test_duplicate_loc_deduplicated(self) -> None:
        body = """<urlset>
          <url><loc>https://x.example/dup</loc></url>
          <url><loc>https://x.example/dup</loc></url>
        </urlset>"""
        parsed = parse_sitemap_xml(body)
        locs = [e.loc for e in parsed.entries]
        assert locs == ["https://x.example/dup"]


class FragmentTrimTests(unittest.TestCase):
    def test_fragment_stripped_from_loc(self) -> None:
        # Spec §URL normalization: "Remove fragments."
        body = """<urlset>
          <url><loc>https://x.example/page#section</loc></url>
        </urlset>"""
        parsed = parse_sitemap_xml(body)
        assert parsed.entries[0].loc == "https://x.example/page"


class MalformedTests(unittest.TestCase):
    def test_no_loc_tags_yields_empty(self) -> None:
        body = "<urlset>no urls here</urlset>"
        parsed = parse_sitemap_xml(body)
        assert parsed.entries == ()

    def test_empty_body_yields_empty(self) -> None:
        parsed = parse_sitemap_xml("")
        assert parsed.kind == "unknown"
        assert parsed.entries == ()

    def test_html_body_yields_unknown_kind(self) -> None:
        # Spec §Negative: HTML returned for /sitemap.xml must NOT
        # yield extracted URLs.
        body = "<html><body><a href=\"/admin\">admin</a></body></html>"
        parsed = parse_sitemap_xml(body)
        assert parsed.kind == "unknown"
        assert parsed.entries == ()

    def test_unclosed_tag_tolerated(self) -> None:
        body = "<urlset><url><loc>https://x.example/incomplete"
        parsed = parse_sitemap_xml(body)
        # Tolerant parser: extract what's clearly present, don't
        # crash on missing close tags.
        assert parsed.kind == "urlset"
        # The loc isn't properly closed, so we shouldn't invent it.
        assert parsed.entries == ()


class WhitespaceTests(unittest.TestCase):
    def test_loc_value_trimmed(self) -> None:
        body = "<urlset><url><loc>  https://x.example/spaced  </loc></url></urlset>"
        parsed = parse_sitemap_xml(body)
        assert parsed.entries[0].loc == "https://x.example/spaced"

    def test_empty_loc_skipped(self) -> None:
        # A url block whose loc is just whitespace or a bare fragment
        # is dropped — fragment-only refs aren't useful path hints.
        body = (
            "<urlset>"
            "<url><loc>#section</loc></url>"
            "<url><loc>https://x.example/real</loc></url>"
            "</urlset>"
        )
        parsed = parse_sitemap_xml(body)
        locs = [e.loc for e in parsed.entries]
        assert locs == ["https://x.example/real"]

    def test_url_block_without_loc_skipped(self) -> None:
        # Malformed real-world sitemap: a <url> block with only
        # metadata and no <loc>. The block is well-formed XML but
        # there's no path hint to extract.
        body = (
            "<urlset>"
            "<url><lastmod>2026-05-19</lastmod></url>"
            "<url><loc>https://x.example/real</loc></url>"
            "</urlset>"
        )
        parsed = parse_sitemap_xml(body)
        locs = [e.loc for e in parsed.entries]
        assert locs == ["https://x.example/real"]
