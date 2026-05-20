"""Pure-function tests for stub 1.13 classify_security_txt.

Composes canonical + legacy FetchOutcomes + ParsedSecurityTxt
into a single Verdict (one of the 10 spec finding types) plus
auxiliary validation_warnings.
"""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from apps.findings.models import FindingStatus

from ..classify import FetchOutcome, classify_security_txt
from ..parser import ParsedSecurityTxt


_NOW = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)
_CANONICAL_URL = "https://x.example/.well-known/security.txt"
_LEGACY_URL = "https://x.example/security.txt"


def _ok(
    body: str = "Contact: mailto:s@x.example\nExpires: 2030-01-01T00:00:00Z\n",
    *, url: str = _CANONICAL_URL,
) -> FetchOutcome:
    return FetchOutcome(
        kind="ok", status=200, body=body, final_url=url,
    )


def _absent(*, status: int = 404, url: str = _CANONICAL_URL) -> FetchOutcome:
    return FetchOutcome(
        kind="absent", status=status, body="", final_url=url,
    )


def _blocked(*, status: int = 403, url: str = _CANONICAL_URL) -> FetchOutcome:
    return FetchOutcome(
        kind="blocked", status=status, body="", final_url=url,
    )


def _parse(
    body: str = "Contact: mailto:s@x.example\nExpires: 2030-01-01T00:00:00Z\n",
) -> ParsedSecurityTxt:
    from ..parser import parse_security_txt
    return parse_security_txt(body)


class MissingTests(unittest.TestCase):
    def test_both_404_yields_missing(self) -> None:
        verdict = classify_security_txt(
            canonical=_absent(), legacy=_absent(url=_LEGACY_URL),
            parsed=None, now=_NOW,
        )
        assert verdict.finding_type == "missing_security_txt"
        assert verdict.confidence == "high"
        assert verdict.finding_status == FindingStatus.CONFIRMED


class BlockedTests(unittest.TestCase):
    def test_403_on_canonical_yields_blocked(self) -> None:
        verdict = classify_security_txt(
            canonical=_blocked(), legacy=_absent(url=_LEGACY_URL),
            parsed=None, now=_NOW,
        )
        assert verdict.finding_type == "blocked_security_txt"
        assert verdict.confidence == "high"


class MalformedTests(unittest.TestCase):
    def test_no_parseable_fields_yields_malformed(self) -> None:
        body = "this is not a security txt at all\njust junk lines\n"
        verdict = classify_security_txt(
            canonical=_ok(body=body), legacy=None,
            parsed=_parse(body), now=_NOW,
        )
        assert verdict.finding_type == "malformed_security_txt"


class NoContactTests(unittest.TestCase):
    def test_no_contact_yields_no_contact(self) -> None:
        body = "Expires: 2030-01-01T00:00:00Z\nPolicy: https://x.example/p\n"
        verdict = classify_security_txt(
            canonical=_ok(body=body), legacy=None,
            parsed=_parse(body), now=_NOW,
        )
        assert verdict.finding_type == "security_txt_no_contact"


class ExpiredTests(unittest.TestCase):
    def test_expired_value_yields_expired(self) -> None:
        body = "Contact: mailto:s@x.example\nExpires: 2020-01-01T00:00:00Z\n"
        verdict = classify_security_txt(
            canonical=_ok(body=body), legacy=None,
            parsed=_parse(body), now=_NOW,
        )
        assert verdict.finding_type == "security_txt_expired"
        assert verdict.confidence == "high"


class MissingExpiresTests(unittest.TestCase):
    def test_no_expires_yields_missing_expires(self) -> None:
        body = "Contact: mailto:s@x.example\n"
        verdict = classify_security_txt(
            canonical=_ok(body=body), legacy=None,
            parsed=_parse(body), now=_NOW,
        )
        assert verdict.finding_type == "security_txt_missing_expires"
        assert verdict.confidence == "medium"


class CanonicalMismatchTests(unittest.TestCase):
    def test_canonical_pointing_elsewhere_yields_mismatch(self) -> None:
        body = (
            "Contact: mailto:s@x.example\n"
            "Expires: 2030-01-01T00:00:00Z\n"
            "Canonical: https://other.example/.well-known/security.txt\n"
        )
        verdict = classify_security_txt(
            canonical=_ok(body=body), legacy=None,
            parsed=_parse(body), now=_NOW,
        )
        assert verdict.finding_type == "security_txt_canonical_mismatch"


class LegacyOnlyTests(unittest.TestCase):
    def test_only_legacy_present_yields_legacy_only(self) -> None:
        body = "Contact: mailto:s@x.example\nExpires: 2030-01-01T00:00:00Z\n"
        verdict = classify_security_txt(
            canonical=_absent(), legacy=_ok(body=body, url=_LEGACY_URL),
            parsed=_parse(body), now=_NOW,
        )
        assert verdict.finding_type == "security_txt_legacy_only"


class ConflictingFilesTests(unittest.TestCase):
    def test_both_present_different_bodies_yields_conflict(self) -> None:
        canonical_body = "Contact: mailto:a@x.example\nExpires: 2030-01-01T00:00:00Z\n"
        legacy_body = "Contact: mailto:b@x.example\nExpires: 2030-01-01T00:00:00Z\n"
        verdict = classify_security_txt(
            canonical=_ok(body=canonical_body),
            legacy=_ok(body=legacy_body, url=_LEGACY_URL),
            parsed=_parse(canonical_body), now=_NOW,
        )
        assert verdict.finding_type == "security_txt_conflicting_files"

    def test_trailing_newline_only_not_treated_as_conflict(self) -> None:
        # _bodies_differ normalises trailing whitespace + final
        # newlines before hashing — without that, a server that
        # serves the same file twice but adds a trailing \n on one
        # would false-positive as conflicting_files.
        body = (
            f"Contact: mailto:s@x.example\n"
            f"Expires: 2030-01-01T00:00:00Z\n"
            f"Canonical: {_CANONICAL_URL}\n"
        )
        canonical_body = body
        legacy_body = body + "\n\n  "  # extra trailing whitespace
        verdict = classify_security_txt(
            canonical=_ok(body=canonical_body),
            legacy=_ok(body=legacy_body, url=_LEGACY_URL),
            parsed=_parse(canonical_body), now=_NOW,
        )
        # Bodies normalise to the same hash → not conflicting.
        assert verdict.finding_type != "security_txt_conflicting_files"


class PresentValidTests(unittest.TestCase):
    def test_clean_file_yields_present_valid(self) -> None:
        body = (
            "Contact: mailto:s@x.example\n"
            "Expires: 2030-01-01T00:00:00Z\n"
            f"Canonical: {_CANONICAL_URL}\n"
        )
        verdict = classify_security_txt(
            canonical=_ok(body=body), legacy=None,
            parsed=_parse(body), now=_NOW,
        )
        assert verdict.finding_type == "security_txt_present_valid"
        assert verdict.finding_status == FindingStatus.CONFIRMED
        assert verdict.confidence == "high"


class IndicatorTests(unittest.TestCase):
    def test_indicators_capture_diagnostic_info(self) -> None:
        body = "Contact: mailto:s@x.example\n"  # no Expires
        verdict = classify_security_txt(
            canonical=_ok(body=body), legacy=None,
            parsed=_parse(body), now=_NOW,
        )
        assert "missing_expires" in " ".join(verdict.indicators)
