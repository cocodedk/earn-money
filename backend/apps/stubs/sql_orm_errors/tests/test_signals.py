"""Matcher contract for stub 1.19 sql_orm_errors.

Each Signature family produces at least one positive hit on its
spec-exemplar text and zero hits on a benign body. The strongest
hit (high > medium > low; ties → first) is returned by
`find_strongest_signal`.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/19-sql-orm-errors.md
"""
from __future__ import annotations

import pytest

from apps.stubs.sql_orm_errors import signals


# --- Positive grid: one exemplar per family ---


POSITIVE_CASES: tuple[tuple[str, bytes], ...] = (
    ("mysql", b"You have an error in your SQL syntax; check the manual"),
    ("mysql", b"<b>Fatal error</b>: mysqli_sql_exception thrown"),
    ("postgresql", b"ERROR: syntax error at or near \"FROM\" at line 1"),
    ("postgresql", b"Npgsql.PostgresException: 42601: syntax error"),
    ("sqlite", b"sqlite3.OperationalError: no such table: users"),
    ("mssql", b"System.Data.SqlClient.SqlException: Invalid column name 'x'."),
    ("oracle", b"ORA-00933: SQL command not properly ended"),
    ("orm", b"SequelizeDatabaseError: column \"foo\" does not exist"),
    ("orm", b"PrismaClientKnownRequestError: P2002 Unique constraint failed"),
    ("orm", b"org.hibernate.HibernateException: query is not valid"),
    ("driver", b"SQLSTATE[42000]: Syntax error or access violation"),
    ("generic_sql", b"unterminated quoted string at character 42"),
    ("other", b"MongoServerError: E11000 duplicate key error"),
)


@pytest.mark.parametrize("expected_family,body", POSITIVE_CASES)
def test_positive_match_per_family(expected_family: str, body: bytes) -> None:
    match = signals.find_strongest_signal(body)
    assert match is not None, f"no match on body={body!r}"
    assert match.signature.family == expected_family, (
        f"expected family={expected_family}, got {match.signature.family} "
        f"via signature_id={match.signature.id}"
    )


# --- Negative grid: bodies with no SQL/ORM signal ---


NEGATIVE_BODIES: tuple[bytes, ...] = (
    b"",                                                       # empty
    b"<html><body>Welcome!</body></html>",                     # plain HTML
    b'{"status":"ok"}',                                        # JSON OK
    b"Hello world",                                            # plain text
    b"Server: nginx/1.21.0\r\n\r\n<h1>Forbidden</h1>",         # 403 page
    b'{"detail":"Not found"}',                                 # 404 DRF
    b"<title>Login</title>",                                   # login page
)


@pytest.mark.parametrize("body", NEGATIVE_BODIES)
def test_negative_no_match(body: bytes) -> None:
    assert signals.find_strongest_signal(body) is None


# --- Priority: strongest hit wins on ties / multi-signal bodies ---


def test_strongest_hit_wins_over_weaker() -> None:
    # 'database error' alone is generic (low). When combined with a
    # high-confidence DBMS exception, the high wins.
    body = b"database error\n\nPDOException: SQLSTATE[42000]: Syntax error"
    match = signals.find_strongest_signal(body)
    assert match is not None
    assert match.signature.confidence_hint == "high"


def test_match_exposes_text_and_offset() -> None:
    body = b"Internal Server Error\n\nSQLSTATE[HY000]: General error"
    match = signals.find_strongest_signal(body)
    assert match is not None
    assert match.matched_text.startswith("SQLSTATE[")
    assert match.offset == body.index(b"SQLSTATE[")


def test_same_rank_subsequent_match_is_skipped() -> None:
    """Cover the `rank > best_rank` False branch: when we already
    have a medium best and find a second medium match later in the
    SIGNATURES order, the second one is skipped (first-wins ties).
    """
    body = b"MariaDB error page: unterminated quoted string at line 5"
    match = signals.find_strongest_signal(body)
    assert match is not None
    # mariadb.banner is in _signatures_relational (earlier than
    # generic_sql.unterminated_string in _signatures_misc), so the
    # first medium-rank hit wins.
    assert match.signature.id == "mariadb.banner"
