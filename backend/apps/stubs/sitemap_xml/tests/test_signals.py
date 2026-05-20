"""Pure-function tests for stub 1.12 sitemap URL signals.

Two families per spec §URL classification + §Deterministic indicators:
- classify_url_scope(loc, base_url) → in_scope | out_of_scope | unknown
- tag_url(loc) → tuple of deterministic hint tags
"""
from __future__ import annotations

import unittest

from ..signals import classify_url_scope, tag_url


class ScopeTests(unittest.TestCase):
    def test_same_origin_in_scope(self) -> None:
        scope = classify_url_scope(
            "https://x.example/page", "https://x.example",
        )
        assert scope == "in_scope"

    def test_relative_path_in_scope(self) -> None:
        # Spec §URL extraction: relative paths preserve as same-origin.
        scope = classify_url_scope("/page", "https://x.example")
        assert scope == "in_scope"

    def test_different_host_out_of_scope(self) -> None:
        scope = classify_url_scope(
            "https://other.example/page", "https://x.example",
        )
        assert scope == "out_of_scope"

    def test_different_scheme_out_of_scope(self) -> None:
        scope = classify_url_scope(
            "http://x.example/page", "https://x.example",
        )
        assert scope == "out_of_scope"

    def test_different_port_out_of_scope(self) -> None:
        scope = classify_url_scope(
            "https://x.example:8443/page", "https://x.example",
        )
        assert scope == "out_of_scope"

    def test_unparseable_loc_yields_unknown(self) -> None:
        # Not relative, no scheme — can't classify confidently.
        # Treat as `unknown` so the runner can decide to drop it.
        scope = classify_url_scope("not a url", "https://x.example")
        assert scope == "unknown"

    def test_empty_loc_yields_unknown(self) -> None:
        assert classify_url_scope("", "https://x.example") == "unknown"


class TagAdminTests(unittest.TestCase):
    def test_admin_path_tagged(self) -> None:
        assert "admin_hint" in tag_url("/admin")

    def test_administrator_path_tagged(self) -> None:
        assert "admin_hint" in tag_url("/administrator/login")

    def test_console_path_tagged(self) -> None:
        assert "admin_hint" in tag_url("/console")


class TagApiTests(unittest.TestCase):
    def test_api_path_tagged(self) -> None:
        assert "api_hint" in tag_url("/api/users")

    def test_graphql_path_tagged(self) -> None:
        assert "api_hint" in tag_url("/graphql")

    def test_swagger_path_tagged(self) -> None:
        assert "api_hint" in tag_url("/swagger/index.html")


class TagDebugTests(unittest.TestCase):
    def test_debug_path_tagged(self) -> None:
        assert "debug_hint" in tag_url("/debug/vars")

    def test_actuator_path_tagged(self) -> None:
        assert "debug_hint" in tag_url("/actuator/env")


class TagBackupTests(unittest.TestCase):
    def test_zip_extension_tagged(self) -> None:
        assert "backup_hint" in tag_url("/dump.zip")

    def test_bak_extension_tagged(self) -> None:
        assert "backup_hint" in tag_url("/db.bak")

    def test_tar_gz_extension_tagged(self) -> None:
        assert "backup_hint" in tag_url("/release.tar.gz")


class TagLegacyTests(unittest.TestCase):
    def test_legacy_path_tagged(self) -> None:
        assert "legacy_hint" in tag_url("/legacy/users")

    def test_v1_path_tagged(self) -> None:
        assert "legacy_hint" in tag_url("/api/v1/users")


class TagTestTests(unittest.TestCase):
    def test_test_path_tagged(self) -> None:
        assert "test_hint" in tag_url("/test/login")

    def test_staging_path_tagged(self) -> None:
        assert "staging_hint" in tag_url("/staging/api")


class TagAuthTests(unittest.TestCase):
    def test_login_path_tagged(self) -> None:
        assert "auth_hint" in tag_url("/login")

    def test_signin_path_tagged(self) -> None:
        assert "auth_hint" in tag_url("/signin")


class TagParameterizedTests(unittest.TestCase):
    def test_query_string_tagged(self) -> None:
        assert "parameterized_url" in tag_url("/page?id=1")

    def test_no_query_string_not_tagged(self) -> None:
        assert "parameterized_url" not in tag_url("/page")


class TagOverlapTests(unittest.TestCase):
    def test_admin_and_api_overlap(self) -> None:
        # /admin/api/users: both hints fire.
        tags = tag_url("/admin/api/users")
        assert "admin_hint" in tags
        assert "api_hint" in tags

    def test_no_hints_for_generic_path(self) -> None:
        assert tag_url("/products/widgets") == ()


class TagCaseInsensitiveTests(unittest.TestCase):
    def test_uppercase_admin_tagged(self) -> None:
        assert "admin_hint" in tag_url("/ADMIN")


class TagEmptyTests(unittest.TestCase):
    def test_empty_path_no_tags(self) -> None:
        assert tag_url("") == ()

    def test_absolute_url_path_extracted(self) -> None:
        # Coverage: tag_url on an absolute URL goes through the
        # urlsplit branch, not the relative-path fast path.
        tags = tag_url("https://x.example/admin/users")
        assert "admin_hint" in tags

    def test_absolute_url_with_no_path_no_tags(self) -> None:
        # Bare origin URL — no path component → no tags.
        assert tag_url("https://x.example") == ()
