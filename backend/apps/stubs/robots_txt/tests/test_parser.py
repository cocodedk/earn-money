"""Pure-function tests for stub 1.11 robots.txt structured parser.

Spec §Body handling + §Robots groups + §Path normalization: turn a
raw robots.txt body into a typed `ParsedRobots` with groups, allow/
disallow path hints, sitemap URLs, and parse warnings.
"""
from __future__ import annotations

import unittest

from ..parser import parse_robots


class BasicDirectiveTests(unittest.TestCase):
    def test_simple_user_agent_and_disallow(self) -> None:
        body = "User-agent: *\nDisallow: /admin\nDisallow: /backup.zip"
        result = parse_robots(body)
        assert len(result.groups) == 1
        group = result.groups[0]
        assert group.user_agents == ("*",)
        assert group.disallows == ("/admin", "/backup.zip")
        assert group.allows == ()

    def test_allow_and_disallow_in_same_group(self) -> None:
        body = "User-agent: *\nAllow: /assets/\nDisallow: /admin"
        result = parse_robots(body)
        assert result.groups[0].allows == ("/assets/",)
        assert result.groups[0].disallows == ("/admin",)

    def test_case_insensitive_directive_names(self) -> None:
        body = "USER-AGENT: *\ndISALLOW: /admin"
        result = parse_robots(body)
        assert result.groups[0].user_agents == ("*",)
        assert result.groups[0].disallows == ("/admin",)


class GroupBoundaryTests(unittest.TestCase):
    def test_new_user_agent_starts_new_group(self) -> None:
        body = (
            "User-agent: bot1\nDisallow: /private\n"
            "User-agent: bot2\nDisallow: /secret"
        )
        result = parse_robots(body)
        assert len(result.groups) == 2
        assert result.groups[0].user_agents == ("bot1",)
        assert result.groups[1].user_agents == ("bot2",)

    def test_consecutive_user_agents_form_one_group(self) -> None:
        body = (
            "User-agent: bot1\nUser-agent: bot2\nDisallow: /shared"
        )
        result = parse_robots(body)
        assert len(result.groups) == 1
        assert result.groups[0].user_agents == ("bot1", "bot2")
        assert result.groups[0].disallows == ("/shared",)


class EmptyDisallowTests(unittest.TestCase):
    def test_empty_disallow_ignored_as_path_hint(self) -> None:
        # Spec §Robots groups: "Empty `Disallow:` means 'nothing
        # disallowed' and must not be recorded as a path hint."
        body = "User-agent: *\nDisallow:\nDisallow: /admin"
        result = parse_robots(body)
        assert result.groups[0].disallows == ("/admin",)


class SitemapTests(unittest.TestCase):
    def test_sitemap_collected_globally(self) -> None:
        body = (
            "User-agent: *\nDisallow: /\n"
            "Sitemap: https://example.com/sitemap.xml"
        )
        result = parse_robots(body)
        assert result.sitemaps == ("https://example.com/sitemap.xml",)

    def test_multiple_sitemaps_collected_in_order(self) -> None:
        body = (
            "Sitemap: https://example.com/a.xml\n"
            "User-agent: *\nDisallow: /admin\n"
            "Sitemap: https://example.com/b.xml"
        )
        result = parse_robots(body)
        assert result.sitemaps == (
            "https://example.com/a.xml",
            "https://example.com/b.xml",
        )

    def test_sitemap_does_not_belong_to_group(self) -> None:
        # Spec: "Sitemap may appear anywhere and is global."
        body = (
            "User-agent: *\nDisallow: /admin\n"
            "Sitemap: https://example.com/sitemap.xml"
        )
        result = parse_robots(body)
        # The group has the disallow only; sitemap is top-level.
        assert result.groups[0].disallows == ("/admin",)
        assert result.sitemaps == ("https://example.com/sitemap.xml",)


class CommentAndBlankLineTests(unittest.TestCase):
    def test_comments_stripped(self) -> None:
        body = (
            "# comment\nUser-agent: *\n# another\n"
            "Disallow: /admin  # inline\nDisallow: /backup"
        )
        result = parse_robots(body)
        # Inline `#` after the value is also a comment.
        assert "/admin" in result.groups[0].disallows
        assert "/backup" in result.groups[0].disallows

    def test_blank_lines_ignored(self) -> None:
        body = "User-agent: *\n\n\nDisallow: /admin\n\n"
        result = parse_robots(body)
        assert result.groups[0].disallows == ("/admin",)


class WildcardPreservationTests(unittest.TestCase):
    def test_wildcards_kept_in_raw_value(self) -> None:
        body = "User-agent: *\nDisallow: /private/*\nDisallow: /*.bak$"
        result = parse_robots(body)
        # Spec §Path normalization rule 3: preserve `*` and `$` raw.
        assert "/private/*" in result.groups[0].disallows
        assert "/*.bak$" in result.groups[0].disallows


class ParseWarningTests(unittest.TestCase):
    def test_unknown_directive_recorded(self) -> None:
        body = "User-agent: *\nGoofy-Directive: nope\nDisallow: /admin"
        result = parse_robots(body)
        # Spec: "Unknown directives must be preserved as
        # unknown_directives but must not fail parsing."
        assert result.groups[0].disallows == ("/admin",)
        assert any("goofy-directive" in w.lower() for w in result.warnings)

    def test_malformed_line_no_colon_recorded(self) -> None:
        body = "User-agent: *\nthis is not a directive\nDisallow: /admin"
        result = parse_robots(body)
        assert "/admin" in result.groups[0].disallows
        assert any("malformed" in w.lower() for w in result.warnings)


class BOMAndEncodingTests(unittest.TestCase):
    def test_utf8_bom_stripped(self) -> None:
        body = "﻿User-agent: *\nDisallow: /admin"
        result = parse_robots(body)
        # The BOM-prefixed line must still match `User-agent:`.
        assert result.groups[0].user_agents == ("*",)


class PathOnlyFilterTests(unittest.TestCase):
    def test_disallow_with_external_url_not_recorded_as_path_hint(
        self,
    ) -> None:
        body = (
            "User-agent: *\nDisallow: https://evil.example/x\n"
            "Disallow: /admin"
        )
        result = parse_robots(body)
        # Spec §Path normalization rule 2: drop full external URLs
        # for path hint purposes. Only `/admin` remains.
        assert result.groups[0].disallows == ("/admin",)


class SupportedButUnconsumedDirectiveTests(unittest.TestCase):
    def test_crawl_delay_parsed_without_warning(self) -> None:
        # crawl-delay/host/clean-param are RECOGNISED — they don't
        # produce a parse warning, but MVP doesn't store their values
        # since they're not part of the discovery surface.
        body = (
            "User-agent: *\nDisallow: /admin\n"
            "Crawl-delay: 10\nHost: example.com\nClean-param: utm_source"
        )
        result = parse_robots(body)
        assert result.groups[0].disallows == ("/admin",)
        # None of crawl-delay/host/clean-param produce warnings — list empty.
        assert result.warnings == ()


class SitemapEdgeCaseTests(unittest.TestCase):
    def test_sitemap_with_empty_value_ignored(self) -> None:
        body = "Sitemap:\nUser-agent: *\nDisallow: /admin"
        result = parse_robots(body)
        assert result.sitemaps == ()
        assert result.groups[0].disallows == ("/admin",)


class OrphanRuleTests(unittest.TestCase):
    def test_disallow_before_any_user_agent_creates_anonymous_group(
        self,
    ) -> None:
        # Some malformed real-world robots files lead with Disallow.
        # Spec doesn't mandate behavior; tolerate by opening an
        # anonymous group rather than crashing or dropping the value.
        body = "Disallow: /admin\nUser-agent: *\nDisallow: /private"
        result = parse_robots(body)
        # First (anonymous) group carries /admin; second carries
        # /private.
        assert len(result.groups) == 2
        assert result.groups[0].user_agents == ()
        assert result.groups[0].disallows == ("/admin",)
        assert result.groups[1].user_agents == ("*",)
        assert result.groups[1].disallows == ("/private",)


class EmptyBodyTests(unittest.TestCase):
    def test_empty_body_yields_no_groups_no_sitemaps(self) -> None:
        result = parse_robots("")
        assert result.groups == ()
        assert result.sitemaps == ()
        assert result.warnings == ()

    def test_whitespace_only_body(self) -> None:
        result = parse_robots("   \n\t\n")
        assert result.groups == ()
        assert result.sitemaps == ()
