"""Pure-function tests for stub 1.13 security.txt parser.

Spec §Parsing: Name: value lines, case-insensitive field names,
repeated fields → list, unknown fields preserved, comments + blank
lines skipped, malformed lines recorded as parse errors.
"""
from __future__ import annotations

import unittest

from ..parser import parse_security_txt


class FieldExtractionTests(unittest.TestCase):
    def test_contact_extracted(self) -> None:
        parsed = parse_security_txt(
            "Contact: mailto:security@example.test"
        )
        assert parsed.contact == ("mailto:security@example.test",)

    def test_multiple_contacts_kept_as_list(self) -> None:
        body = (
            "Contact: mailto:a@example.test\n"
            "Contact: mailto:b@example.test\n"
        )
        parsed = parse_security_txt(body)
        assert parsed.contact == (
            "mailto:a@example.test",
            "mailto:b@example.test",
        )

    def test_expires_extracted(self) -> None:
        parsed = parse_security_txt("Expires: 2027-01-01T00:00:00Z")
        assert parsed.expires == ("2027-01-01T00:00:00Z",)

    def test_canonical_extracted(self) -> None:
        parsed = parse_security_txt(
            "Canonical: https://example.test/.well-known/security.txt"
        )
        assert parsed.canonical == (
            "https://example.test/.well-known/security.txt",
        )

    def test_all_known_fields_recognised(self) -> None:
        body = (
            "Contact: mailto:a@x.test\n"
            "Expires: 2027-01-01T00:00:00Z\n"
            "Encryption: https://x.test/pgp.asc\n"
            "Acknowledgments: https://x.test/thanks\n"
            "Preferred-Languages: en, da\n"
            "Canonical: https://x.test/.well-known/security.txt\n"
            "Policy: https://x.test/disclosure\n"
            "Hiring: https://x.test/careers\n"
            "CSAF: https://x.test/.well-known/csaf/provider.json\n"
        )
        parsed = parse_security_txt(body)
        assert parsed.contact == ("mailto:a@x.test",)
        assert parsed.encryption == ("https://x.test/pgp.asc",)
        assert parsed.acknowledgments == ("https://x.test/thanks",)
        assert parsed.preferred_languages == ("en, da",)
        assert parsed.policy == ("https://x.test/disclosure",)
        assert parsed.hiring == ("https://x.test/careers",)
        assert parsed.csaf == (
            "https://x.test/.well-known/csaf/provider.json",
        )


class CaseInsensitiveTests(unittest.TestCase):
    def test_uppercase_field_name_recognised(self) -> None:
        parsed = parse_security_txt("CONTACT: mailto:a@x.test")
        assert parsed.contact == ("mailto:a@x.test",)

    def test_mixed_case_field_name_recognised(self) -> None:
        parsed = parse_security_txt("CoNtAcT: mailto:a@x.test")
        assert parsed.contact == ("mailto:a@x.test",)


class WhitespaceTests(unittest.TestCase):
    def test_value_trimmed(self) -> None:
        parsed = parse_security_txt("Contact:    mailto:a@x.test   ")
        assert parsed.contact == ("mailto:a@x.test",)

    def test_blank_lines_ignored(self) -> None:
        body = (
            "\n\n"
            "Contact: mailto:a@x.test\n"
            "\n"
            "Expires: 2027-01-01T00:00:00Z\n"
        )
        parsed = parse_security_txt(body)
        assert parsed.contact == ("mailto:a@x.test",)
        assert parsed.expires == ("2027-01-01T00:00:00Z",)


class CommentTests(unittest.TestCase):
    def test_comment_line_ignored(self) -> None:
        body = (
            "# This is a comment\n"
            "Contact: mailto:a@x.test\n"
            "# Another comment\n"
        )
        parsed = parse_security_txt(body)
        assert parsed.contact == ("mailto:a@x.test",)

    def test_leading_whitespace_before_comment_marker_still_comment(
        self,
    ) -> None:
        body = "  # indented comment\nContact: mailto:a@x.test\n"
        parsed = parse_security_txt(body)
        assert parsed.contact == ("mailto:a@x.test",)


class UnknownFieldTests(unittest.TestCase):
    def test_unknown_field_preserved(self) -> None:
        body = (
            "Contact: mailto:a@x.test\n"
            "X-Custom-Header: value123\n"
        )
        parsed = parse_security_txt(body)
        assert parsed.unknown_fields == (("X-Custom-Header", "value123"),)

    def test_unknown_field_does_not_stop_parsing(self) -> None:
        body = (
            "X-Custom: weird\n"
            "Contact: mailto:a@x.test\n"
        )
        parsed = parse_security_txt(body)
        # Both must be captured.
        assert parsed.contact == ("mailto:a@x.test",)
        assert parsed.unknown_fields == (("X-Custom", "weird"),)


class MalformedLineTests(unittest.TestCase):
    def test_line_without_colon_recorded_as_error(self) -> None:
        body = (
            "this is not a field\n"
            "Contact: mailto:a@x.test\n"
        )
        parsed = parse_security_txt(body)
        assert parsed.contact == ("mailto:a@x.test",)
        assert any("not a field" in e or "malformed" in e.lower()
                   for e in parsed.parse_errors)

    def test_empty_value_recorded_as_error(self) -> None:
        body = (
            "Contact:\n"
            "Contact: mailto:b@x.test\n"
        )
        parsed = parse_security_txt(body)
        # The valid contact survives.
        assert "mailto:b@x.test" in parsed.contact
        # The empty value is an error, not a contact.
        assert "" not in parsed.contact
        assert len(parsed.parse_errors) >= 1


class EmptyBodyTests(unittest.TestCase):
    def test_empty_body_yields_empty_parse(self) -> None:
        parsed = parse_security_txt("")
        assert parsed.contact == ()
        assert parsed.unknown_fields == ()
        assert parsed.parse_errors == ()

    def test_only_comments_yields_empty_parse(self) -> None:
        body = "# header\n# more header\n"
        parsed = parse_security_txt(body)
        assert parsed.contact == ()
