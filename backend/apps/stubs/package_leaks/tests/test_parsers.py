"""Parser tests for stub 1.5 package-version-leaks.

Two MVP parsers: package.json (JSON) and requirements.txt (line-based).
Each returns a list of {package, version, source_kind} dicts. On
malformed input, parsers degrade to empty list rather than raising.
"""
from __future__ import annotations

import unittest

from ..parsers.package_json import parse_package_json
from ..parsers.requirements_txt import parse_requirements_txt


class PackageJsonParserTests(unittest.TestCase):
    def test_extracts_name_and_version(self) -> None:
        body = '{"name": "my-app", "version": "1.2.3"}'
        hits = parse_package_json(body)
        assert {"package": "my-app", "version": "1.2.3",
                "source_kind": "package.json"} in hits

    def test_extracts_dependencies(self) -> None:
        body = """
        {
          "name": "my-app",
          "version": "1.0.0",
          "dependencies": {
            "lodash": "^4.17.21",
            "react": "17.0.2"
          }
        }
        """
        hits = parse_package_json(body)
        pkgs = {(h["package"], h["version"]) for h in hits}
        assert ("lodash", "^4.17.21") in pkgs
        assert ("react", "17.0.2") in pkgs
        assert ("my-app", "1.0.0") in pkgs

    def test_extracts_dev_dependencies(self) -> None:
        body = """
        {
          "name": "x",
          "version": "1.0",
          "devDependencies": {"pytest": "8.0.0"}
        }
        """
        hits = parse_package_json(body)
        pkgs = {h["package"] for h in hits}
        assert "pytest" in pkgs

    def test_malformed_json_yields_empty(self) -> None:
        assert parse_package_json("not json") == []
        assert parse_package_json("{broken: json}") == []

    def test_empty_string_yields_empty(self) -> None:
        assert parse_package_json("") == []

    def test_non_object_root_yields_empty(self) -> None:
        # A JSON array root isn't a package.json shape.
        assert parse_package_json('["just", "an", "array"]') == []

    def test_non_string_name_or_version_is_skipped(self) -> None:
        # Malformed package.json: numeric version. Don't fabricate a
        # finding by str()-ing it.
        body = '{"name": "x", "version": 1.0, "dependencies": {}}'
        hits = parse_package_json(body)
        # The root entry is dropped; the (empty) deps dict adds nothing.
        assert hits == []

    def test_non_string_dependency_value_skipped(self) -> None:
        body = (
            '{"name": "x", "version": "1.0",'
            ' "dependencies": {"good": "1.0", "bad": 2.0}}'
        )
        hits = parse_package_json(body)
        pkgs = {h["package"] for h in hits}
        assert "good" in pkgs
        assert "bad" not in pkgs

    def test_non_dict_dependencies_skipped(self) -> None:
        body = '{"name": "x", "version": "1.0", "dependencies": "not-a-dict"}'
        hits = parse_package_json(body)
        assert hits == [
            {"package": "x", "version": "1.0", "source_kind": "package.json"}
        ]


class RequirementsTxtParserTests(unittest.TestCase):
    def test_pinned_versions(self) -> None:
        body = """
        Django==5.1.0
        requests==2.31.0
        pytest==8.0.0
        """
        hits = parse_requirements_txt(body)
        pkgs = {(h["package"], h["version"]) for h in hits}
        assert ("Django", "5.1.0") in pkgs
        assert ("requests", "2.31.0") in pkgs
        assert ("pytest", "8.0.0") in pkgs

    def test_skips_comments_and_blanks(self) -> None:
        body = """
        # comment line
        Django==5.1.0

        # another comment
        """
        hits = parse_requirements_txt(body)
        assert len(hits) == 1
        assert hits[0]["package"] == "Django"

    def test_skips_lines_without_exact_pin(self) -> None:
        # Per MVP scope, we only emit findings for `==` pins.
        # `>=`, `~=`, etc., are version constraints — not leaks of an
        # exact installed version.
        body = """
        Django>=5.0
        requests~=2.31
        pytest==8.0.0
        """
        hits = parse_requirements_txt(body)
        packages = {h["package"] for h in hits}
        assert packages == {"pytest"}

    def test_empty_string_yields_empty(self) -> None:
        assert parse_requirements_txt("") == []

    def test_source_kind_marker(self) -> None:
        hits = parse_requirements_txt("foo==1.0.0")
        assert hits == [{"package": "foo", "version": "1.0.0",
                         "source_kind": "requirements.txt"}]
