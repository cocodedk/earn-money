"""Classifier contract for stub 1.19 sql_orm_errors.

Spec §Classification confidence ladder + §Status rules:

| confidence | required evidence                                                 |
| ---------- | ----------------------------------------------------------------- |
| high       | strong signature (requires_context=False) + error-status (≥400)   |
|            | OR strong signature + SQL fragment / driver / table-column lift   |
| medium     | strong signature alone (requires_context=False, no error status)  |
|            | OR signature.confidence_hint=medium + error_status                |
| low        | weak signature (requires_context=True, no context lift)           |
| none       | no signature match → return None (no Verdict, no Finding)         |

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/19-sql-orm-errors.md
"""
from __future__ import annotations

import pytest

from apps.stubs.sql_orm_errors import classify as cls


# --- Positive ladder ---


def test_strong_signature_with_error_status_is_high() -> None:
    body = b"500 Internal Server Error\n\nYou have an error in your SQL syntax near 'FROM users WHERE id='"
    v = cls.classify(status=500, body=body)
    assert v is not None
    assert v.confidence == "high"
    assert v.signature_id == "mysql.syntax_error"


def test_strong_signature_with_ok_status_is_medium() -> None:
    # No error status (200) — high-hint signature alone collapses to medium.
    body = b"PrismaClientKnownRequestError: P2002"
    v = cls.classify(status=200, body=body)
    assert v is not None
    assert v.confidence == "medium"


def test_medium_hint_signature_without_context_is_low() -> None:
    body = b"X-Server: MariaDB"  # mariadb.banner has confidence_hint=medium + requires_context=True
    v = cls.classify(status=200, body=body)
    assert v is not None
    assert v.confidence == "low"


def test_weak_signature_alone_is_low() -> None:
    body = b"database error"
    v = cls.classify(status=500, body=body)
    assert v is not None
    assert v.confidence == "low"


# --- Negative grid ---


def test_no_match_returns_none() -> None:
    assert cls.classify(status=200, body=b"<html>OK</html>") is None


def test_rfc7807_problem_json_without_signature_is_none() -> None:
    body = b'{"type":"about:blank","title":"Internal Server Error","status":500,"detail":"internal error"}'
    assert cls.classify(status=500, body=body) is None


def test_server_header_alone_is_none() -> None:
    # "Server: nginx" alone doesn't trigger any signature.
    body = b"<h1>Forbidden</h1>"
    assert cls.classify(status=403, body=body) is None


# --- Verdict structure ---


def test_verdict_carries_signal_kind_excerpt_severity() -> None:
    body = b"Error: SQLSTATE[42000]: Syntax error or access violation: 1064"
    v = cls.classify(status=500, body=body)
    assert v is not None
    assert v.signature_id == "driver.sqlstate"
    assert v.signature_family == "driver"
    assert "SQLSTATE[42000]" in v.error_excerpt
    assert v.severity in ("info", "low", "medium")


def test_verdict_severity_never_exceeds_medium() -> None:
    """Spec §Severity guidance: severity must NOT be high/critical for
    this check alone. Sample every positive test case via parametrize."""
    bodies = (
        b"You have an error in your SQL syntax",
        b"sqlite3.OperationalError: no such table",
        b"ORA-00933",
        b"SequelizeDatabaseError: column foo",
        b"SQLSTATE[42000]",
    )
    for body in bodies:
        v = cls.classify(status=500, body=body)
        assert v is not None
        assert v.severity in ("info", "low", "medium"), \
            f"severity={v.severity} for body={body!r} exceeds spec cap"


# --- Documented coverage gap ---


def test_django_orm_path_currently_unmatched() -> None:
    """Records a known coverage gap: `django.db.utils.OperationalError`
    + "relation X does not exist" should arguably match but no current
    signature catches it. Tracked for a future signature addition; this
    test pins the current behavior so a regression is detected."""
    body = b"django.db.utils.OperationalError: relation \"foo\" does not exist"
    assert cls.classify(status=500, body=body) is None
