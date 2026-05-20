"""Pure-function tests for stub 1.11 sensitive-path matching + origin
classification."""
from __future__ import annotations

import unittest

from ..signals import classify_sitemap_origin, is_sensitive_path


class SensitivePathSegmentMatchTests(unittest.TestCase):
    def test_admin_segment_matches(self) -> None:
        assert "admin" in is_sensitive_path("/admin")

    def test_trailing_slash_segment_matches(self) -> None:
        assert "private" in is_sensitive_path("/private/")

    def test_dot_git_segment_matches(self) -> None:
        # Spec lists `.git` as a sensitive segment. Keep the leading
        # dot intact via the whole-segment check, not the dot-split
        # path.
        assert ".git" in is_sensitive_path("/.git/")

    def test_dot_env_segment_matches(self) -> None:
        assert ".env" in is_sensitive_path("/.env")


class FilenameComponentMatchTests(unittest.TestCase):
    def test_backup_zip_matches_backup_token(self) -> None:
        result = is_sensitive_path("/backup.zip")
        assert "backup" in result

    def test_config_old_matches_both_tokens(self) -> None:
        result = is_sensitive_path("/config.old")
        assert "config" in result
        assert "old" in result

    def test_db_dump_sql_matches_three_tokens(self) -> None:
        result = is_sensitive_path("/db-dump.sql")
        # All three components should match: db, dump, sql.
        assert "db" in result
        assert "dump" in result
        assert "sql" in result


class NonSensitivePathTests(unittest.TestCase):
    def test_blog_returns_empty(self) -> None:
        assert is_sensitive_path("/blog") == ()

    def test_catalog_returns_empty(self) -> None:
        assert is_sensitive_path("/catalog") == ()

    def test_asset_logo_returns_empty(self) -> None:
        # Spec §"Examples that should not match" — /assets/logo.svg.
        assert is_sensitive_path("/assets/logo.svg") == ()

    def test_gold_does_not_match_old(self) -> None:
        # The "old" trap from stub 1.9 — a segment that CONTAINS
        # "old" must not match unless "old" appears as its own
        # component.
        assert is_sensitive_path("/products/gold") == ()


class CaseInsensitiveTests(unittest.TestCase):
    def test_uppercase_admin_matches(self) -> None:
        assert "admin" in is_sensitive_path("/ADMIN")

    def test_mixed_case_secrets_matches(self) -> None:
        result = is_sensitive_path("/Secrets/Db.SQL")
        assert "secrets" in result
        assert "db" in result
        assert "sql" in result


class EmptyPathTests(unittest.TestCase):
    def test_empty_path_returns_empty(self) -> None:
        assert is_sensitive_path("") == ()

    def test_root_returns_empty(self) -> None:
        assert is_sensitive_path("/") == ()


class DeduplicationTests(unittest.TestCase):
    def test_repeated_token_returned_once(self) -> None:
        # /admin/admin should yield "admin" exactly once — downstream
        # counts and arrays expect a deduplicated indicators list.
        result = is_sensitive_path("/admin/admin")
        assert result.count("admin") == 1


class DeterministicOrderTests(unittest.TestCase):
    def test_multi_token_segment_left_to_right_order(self) -> None:
        # `db-dump.sql` is a single segment that contains three
        # tokens. Spec doesn't require an order but the docstring
        # promises first-encounter (left-to-right). A previous
        # set-based implementation leaked hash randomization into
        # the result.
        result = is_sensitive_path("/db-dump.sql")
        # Filter to just the tokens we know match (in case future
        # token-list additions change membership).
        observed = [t for t in result if t in {"db", "dump", "sql"}]
        assert observed == ["db", "dump", "sql"]


class SitemapOriginTests(unittest.TestCase):
    def test_same_host_and_scheme_is_same_origin(self) -> None:
        assert classify_sitemap_origin(
            "https://example.com/sitemap.xml",
            "https://example.com",
        ) == "same_origin"

    def test_different_host_is_cross_origin(self) -> None:
        assert classify_sitemap_origin(
            "https://other.example/sitemap.xml",
            "https://example.com",
        ) == "cross_origin"

    def test_different_scheme_is_cross_origin(self) -> None:
        # http vs https is a different origin per RFC 6454.
        assert classify_sitemap_origin(
            "http://example.com/sitemap.xml",
            "https://example.com",
        ) == "cross_origin"

    def test_different_port_is_cross_origin(self) -> None:
        assert classify_sitemap_origin(
            "https://example.com:8443/sitemap.xml",
            "https://example.com",
        ) == "cross_origin"

    def test_malformed_sitemap_url_is_cross_origin(self) -> None:
        # A relative or malformed sitemap URL can't be confirmed
        # as same-origin — surface as cross_origin so the runner
        # doesn't accidentally trust it.
        assert classify_sitemap_origin(
            "not a url",
            "https://example.com",
        ) == "cross_origin"
