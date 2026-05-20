"""Classifier contract for stub `well_known_paths`.

Per-family Verdict resolver: status guard + body signature → confidence.

Spec sources: 1.20-1.25 §Classification.
"""
from __future__ import annotations

from apps.findings.models import Severity
from apps.stubs.well_known_paths import families
from apps.stubs.well_known_paths.classify import classify


def _env(): return families.get_family("env")
def _git(): return families.get_family("git")
def _archives(): return families.get_family("backup_archives")
def _dbs(): return families.get_family("db_dumps")


# --- Positive grid ---


def test_env_kv_body_yields_high_verdict() -> None:
    fam = _env()
    v = classify(
        status=200,
        body=b"DB_PASSWORD=secret\nAPI_KEY=abc123\n",
        family=fam.family,
        signatures=fam.signatures,
        severity_hint=fam.severity_hint,
    )
    assert v is not None
    assert v.confidence == "high"
    assert v.family == "env"
    assert v.severity == Severity.MEDIUM


def test_git_head_ref_yields_high_verdict() -> None:
    fam = _git()
    v = classify(
        status=200, body=b"ref: refs/heads/main\n",
        family=fam.family, signatures=fam.signatures,
        severity_hint=fam.severity_hint,
    )
    assert v is not None
    assert v.signature_id == "git.head_ref"


def test_zip_magic_yields_high_verdict() -> None:
    fam = _archives()
    body = bytes.fromhex("504b0304") + b"\x00" * 100  # PK..
    v = classify(
        status=200, body=body, family=fam.family,
        signatures=fam.signatures, severity_hint=fam.severity_hint,
    )
    assert v is not None
    assert v.signature_id == "archive.zip"
    assert v.severity == Severity.MEDIUM


def test_sqlite_magic_yields_high_verdict() -> None:
    fam = _dbs()
    body = b"SQLite format 3\x00" + b"\x00" * 100
    v = classify(
        status=206, body=body, family=fam.family,
        signatures=fam.signatures, severity_hint=fam.severity_hint,
    )
    assert v is not None
    assert v.signature_id == "db.sqlite_magic"


# --- Negative grid ---


def test_non_2xx_status_returns_none() -> None:
    fam = _env()
    v = classify(
        status=404, body=b"DB_PASSWORD=x",
        family=fam.family, signatures=fam.signatures,
        severity_hint=fam.severity_hint,
    )
    assert v is None


def test_empty_body_returns_none() -> None:
    fam = _env()
    v = classify(
        status=200, body=b"",
        family=fam.family, signatures=fam.signatures,
        severity_hint=fam.severity_hint,
    )
    assert v is None


def test_no_signature_match_returns_none() -> None:
    fam = _env()
    v = classify(
        status=200, body=b"<html><body>Welcome</body></html>",
        family=fam.family, signatures=fam.signatures,
        severity_hint=fam.severity_hint,
    )
    assert v is None


def test_zip_magic_mismatch_yields_none() -> None:
    fam = _archives()
    # Body starts with HTML, not ZIP magic — classifier rejects.
    v = classify(
        status=200, body=b"<!DOCTYPE html><html>",
        family=fam.family, signatures=fam.signatures,
        severity_hint=fam.severity_hint,
    )
    assert v is None


# --- Severity collapse for low-confidence hits ---


def test_low_confidence_collapses_to_info() -> None:
    """Synthetic family with a single low-confidence signature should
    yield Severity.INFO regardless of family hint."""
    from apps.stubs.well_known_paths._types import Signature
    sig = Signature(
        id="test.weak", family="logs", pattern=r"\bweak\b",
        pattern_type="regex", case_sensitive=False,
        confidence_hint="low", description="test",
    )
    v = classify(
        status=200, body=b"this is a weak signal",
        family="logs", signatures=(sig,),
        severity_hint=Severity.MEDIUM,
    )
    assert v is not None
    assert v.confidence == "low"
    assert v.severity == Severity.INFO
