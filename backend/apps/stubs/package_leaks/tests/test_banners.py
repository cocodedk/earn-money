"""Banner-regex tests for stub 1.5 package-version-leaks.

The banner scanner finds package + version disclosures in JS/CSS
minified-bundle banners like:

    /*! lodash 4.17.21 */
    /*! react v17.0.2 */
    /** @license MIT vue 3.2.31 */

A match requires a package-like token AND a version-like token close
together — `Description containing version 1.2.3` in prose must NOT
match (false-positive guard from the spec).
"""
from __future__ import annotations

import unittest

from ..banners import scan_banners


class CommonBannerForms(unittest.TestCase):
    def test_lodash_short_banner(self) -> None:
        text = "/*! lodash 4.17.21 */"
        hits = scan_banners(text)
        assert hits == [{"package": "lodash", "version": "4.17.21", "source_kind": "banner"}]

    def test_multiline_banner(self) -> None:
        text = """
            /*!
             * react 17.0.2
             */
        """
        hits = scan_banners(text)
        assert {"package": "react", "version": "17.0.2",
                "source_kind": "banner"} in hits

    def test_license_banner_with_v_prefix(self) -> None:
        text = "/** @license React v17.0.2 */"
        hits = scan_banners(text)
        assert {"package": "React", "version": "17.0.2",
                "source_kind": "banner"} in hits

    def test_jquery_short_banner(self) -> None:
        text = "/*! jQuery v3.7.1 */"
        hits = scan_banners(text)
        assert {"package": "jQuery", "version": "3.7.1",
                "source_kind": "banner"} in hits


class FalsePositiveGuard(unittest.TestCase):
    def test_prose_with_version_doesnt_match(self) -> None:
        # The spec rejects "describing version 1.2.3" in prose. The
        # banner regex anchors on the /*! or /** comment marker so
        # plain prose doesn't fire.
        text = "Hi! Our software supports version 1.2.3 of the API."
        assert scan_banners(text) == []

    def test_html_text_without_banner_form_doesnt_match(self) -> None:
        text = "<p>Powered by Bootstrap 5.3.0</p>"
        assert scan_banners(text) == []

    def test_empty_text_yields_empty(self) -> None:
        assert scan_banners("") == []


class MultiplePackagesInOneFile(unittest.TestCase):
    def test_multiple_banners_in_one_bundle(self) -> None:
        text = """
            /*! lodash 4.17.21 */
            // ... minified code ...
            /*! moment 2.29.4 */
            // ... more code ...
            /*! axios 1.6.2 */
        """
        hits = scan_banners(text)
        pkgs = {(h["package"], h["version"]) for h in hits}
        assert ("lodash", "4.17.21") in pkgs
        assert ("moment", "2.29.4") in pkgs
        assert ("axios", "1.6.2") in pkgs


class ScopedPackageNames(unittest.TestCase):
    def test_npm_scoped_name(self) -> None:
        text = "/*! @angular/core 16.2.0 */"
        hits = scan_banners(text)
        assert {"package": "@angular/core", "version": "16.2.0",
                "source_kind": "banner"} in hits


class ReservedNamesFiltered(unittest.TestCase):
    def test_at_license_alone_is_skipped(self) -> None:
        # A banner that captures `@license` as the package name (no real
        # package after it) shouldn't fire a finding. The regex would
        # otherwise match `@license 1.0.0` → package=@license.
        text = "/*! @license 1.0.0 */"
        assert scan_banners(text) == []


class DeduplicationTests(unittest.TestCase):
    def test_duplicate_banners_collapsed(self) -> None:
        text = (
            "/*! lodash 4.17.21 */"
            "/*! lodash 4.17.21 */"
        )
        hits = scan_banners(text)
        assert hits == [{"package": "lodash", "version": "4.17.21", "source_kind": "banner"}]
