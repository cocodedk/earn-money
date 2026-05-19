"""Tests for stub 1.6 robots.txt and sitemap.xml extractors."""
from __future__ import annotations

import unittest

from ..extractors.robots_txt import parse_robots_txt
from ..extractors.sitemap_xml import parse_sitemap_xml


class RobotsTxtTests(unittest.TestCase):
    def test_extracts_disallow_paths(self) -> None:
        body = """
        User-agent: *
        Disallow: /admin
        Disallow: /private/
        Allow: /
        """
        paths = parse_robots_txt(body)
        assert "/admin" in paths
        assert "/private/" in paths

    def test_ignores_allow_and_user_agent(self) -> None:
        body = """
        User-agent: *
        Allow: /
        Disallow: /admin
        """
        paths = parse_robots_txt(body)
        assert paths == ["/admin"]

    def test_skips_comments_and_blanks(self) -> None:
        body = """
        # robots.txt for example.com

        Disallow: /admin
        # comment line
        """
        paths = parse_robots_txt(body)
        assert paths == ["/admin"]

    def test_empty_input_yields_empty(self) -> None:
        assert parse_robots_txt("") == []

    def test_disallow_with_no_value_skipped(self) -> None:
        # `Disallow:` with empty value means "nothing disallowed" per
        # the RFC. Shouldn't add an empty string to the list.
        body = "User-agent: *\nDisallow:\n"
        assert parse_robots_txt(body) == []

    def test_case_insensitive_directive(self) -> None:
        # Real-world robots.txt uses inconsistent casing.
        body = "DISALLOW: /admin\ndisallow: /private/"
        paths = parse_robots_txt(body)
        assert "/admin" in paths
        assert "/private/" in paths


class SitemapXmlTests(unittest.TestCase):
    def test_extracts_loc_paths_same_origin(self) -> None:
        body = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://x.example/foo</loc></url>
          <url><loc>https://x.example/bar/</loc></url>
        </urlset>
        """
        paths = parse_sitemap_xml(body, base_url="https://x.example/")
        assert "/foo" in paths
        assert "/bar/" in paths

    def test_filters_cross_origin(self) -> None:
        body = """<?xml version="1.0"?>
        <urlset>
          <loc>https://x.example/keep</loc>
          <loc>https://other.example/drop</loc>
        </urlset>
        """
        paths = parse_sitemap_xml(body, base_url="https://x.example/")
        assert paths == ["/keep"]

    def test_relative_path_loc_preserved(self) -> None:
        body = "<urlset><loc>/relative-path</loc></urlset>"
        paths = parse_sitemap_xml(body, base_url="https://x.example/")
        assert "/relative-path" in paths

    def test_malformed_xml_returns_empty(self) -> None:
        # XML parsing must tolerate broken input — return [] rather
        # than raising.
        assert parse_sitemap_xml("<not really xml", base_url="https://x.example/") == []

    def test_empty_input_yields_empty(self) -> None:
        assert parse_sitemap_xml("", base_url="https://x.example/") == []

    def test_deduplicates_identical_locs(self) -> None:
        body = "<urlset><loc>/dup</loc><loc>/dup</loc></urlset>"
        paths = parse_sitemap_xml(body, base_url="https://x.example/")
        assert paths == ["/dup"]
