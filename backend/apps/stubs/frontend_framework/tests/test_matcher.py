"""Tests for the stub 1.3 matcher.

The matcher operates on an EvidenceBundle:
  {
    "html_body": str,
    "script_paths": list[str],
    "asset_bodies": dict[str, str],  # filename → body
  }

It dispatches on signature["source"] to pick which slice of the bundle
to match against.
"""
from __future__ import annotations

import unittest

from ..matcher import extract_version, match_signatures


BUNDLE_EMPTY: dict = {
    "html_body": "",
    "script_paths": [],
    "asset_bodies": {},
}


SIG_NG_VERSION = {
    "id": "angular_ng_version",
    "technology": "Angular",
    "category": "framework",
    "source": "html_body",
    "match_type": "regex",
    "value_pattern": r'ng-version="[\d.]+"',
    "version_regex": r'ng-version="([\d.]+)"',
    "confidence": "high",
}

SIG_JQUERY_PATH = {
    "id": "jquery_script_path",
    "technology": "jQuery",
    "category": "library",
    "source": "script_src_path",
    "match_type": "regex",
    "value_pattern": r"jquery(?:-[\d.]+)?(?:\.min)?\.js",
    "version_regex": r"jquery-([\d.]+)(?:\.min)?\.js",
    "confidence": "medium",
}

SIG_REACT_DOM = {
    "id": "react_dom_in_asset",
    "technology": "React",
    "category": "framework",
    "source": "asset_body",
    "match_type": "contains",
    "value_pattern": "react-dom",
    "version_regex": None,
    "confidence": "medium",
}

SIG_NGCONTENT = {
    "id": "angular_ngcontent_marker",
    "technology": "Angular",
    "category": "framework",
    "source": "html_body",
    "match_type": "contains_all",
    "value_pattern": ["_ngcontent-", "-ng-"],
    "version_regex": None,
    "confidence": "medium",
}


class HtmlBodyMatcherTests(unittest.TestCase):
    def test_regex_on_body(self) -> None:
        bundle = {**BUNDLE_EMPTY, "html_body": '<app-root ng-version="16.2.0">'}
        assert match_signatures([SIG_NG_VERSION], bundle) == [SIG_NG_VERSION]

    def test_no_match_on_empty_body(self) -> None:
        assert match_signatures([SIG_NG_VERSION], BUNDLE_EMPTY) == []

    def test_contains_all_requires_every_pattern(self) -> None:
        bundle = {
            **BUNDLE_EMPTY,
            "html_body": '<div _ngcontent-abc="" -ng-zone="">',
        }
        assert match_signatures([SIG_NGCONTENT], bundle) == [SIG_NGCONTENT]

    def test_contains_all_misses_when_one_pattern_absent(self) -> None:
        bundle = {**BUNDLE_EMPTY, "html_body": "_ngcontent-abc only"}
        assert match_signatures([SIG_NGCONTENT], bundle) == []


class ScriptSrcPathMatcherTests(unittest.TestCase):
    def test_regex_on_any_script_path(self) -> None:
        bundle = {
            **BUNDLE_EMPTY,
            "script_paths": ["/static/jquery-3.7.1.min.js"],
        }
        assert match_signatures([SIG_JQUERY_PATH], bundle) == [SIG_JQUERY_PATH]

    def test_no_match_when_no_path_matches(self) -> None:
        bundle = {**BUNDLE_EMPTY, "script_paths": ["/static/main.js"]}
        assert match_signatures([SIG_JQUERY_PATH], bundle) == []

    def test_no_match_when_script_paths_empty(self) -> None:
        # Empty haystacks (no script_paths) — distinct from "paths exist
        # but none match" because the matcher short-circuits before
        # iterating patterns.
        assert match_signatures([SIG_JQUERY_PATH], BUNDLE_EMPTY) == []


class AssetBodyMatcherTests(unittest.TestCase):
    def test_contains_on_any_asset_body(self) -> None:
        bundle = {
            **BUNDLE_EMPTY,
            "asset_bodies": {
                "vendor.js": "function react-dom(){...}",
                "app.js": "console.log('hi')",
            },
        }
        assert match_signatures([SIG_REACT_DOM], bundle) == [SIG_REACT_DOM]

    def test_no_match_when_no_asset_body_contains_pattern(self) -> None:
        bundle = {**BUNDLE_EMPTY, "asset_bodies": {"app.js": "no react here"}}
        assert match_signatures([SIG_REACT_DOM], bundle) == []


class ExtractVersionTests(unittest.TestCase):
    def test_extracts_from_html_body(self) -> None:
        bundle = {**BUNDLE_EMPTY, "html_body": 'ng-version="16.2.0"'}
        assert extract_version(SIG_NG_VERSION, bundle) == "16.2.0"

    def test_extracts_from_script_path(self) -> None:
        bundle = {
            **BUNDLE_EMPTY,
            "script_paths": ["/static/jquery-3.7.1.min.js"],
        }
        assert extract_version(SIG_JQUERY_PATH, bundle) == "3.7.1"

    def test_none_when_no_version_regex(self) -> None:
        assert extract_version(SIG_REACT_DOM, BUNDLE_EMPTY) is None

    def test_none_when_regex_does_not_match(self) -> None:
        bundle = {**BUNDLE_EMPTY, "html_body": "no version here"}
        assert extract_version(SIG_NG_VERSION, bundle) is None
