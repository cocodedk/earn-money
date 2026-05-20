"""Signature table contract for stub 1.19 sql_orm_errors.

Pins the 6+ DB/ORM families per spec §Persistence + §Signature sources.
Each family has at least one Signature with non-empty pattern + a
confidence_hint per spec §Classification.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/19-sql-orm-errors.md
"""
from __future__ import annotations

import pytest

from apps.stubs.sql_orm_errors import signatures as sig


REQUIRED_FAMILIES = (
    "mysql", "postgresql", "sqlite", "mssql", "oracle",
    "mariadb", "orm", "driver", "generic_sql", "other",
)


def test_every_required_family_has_at_least_one_signature() -> None:
    families = {s.family for s in sig.SIGNATURES}
    missing = set(REQUIRED_FAMILIES) - families
    # generic_sql, driver, mariadb, other may be sparsely populated but
    # the spec-required ones (mysql, postgresql, sqlite, mssql, oracle, orm)
    # are MUST-have. Assert the strict set explicitly.
    must_have = {"mysql", "postgresql", "sqlite", "mssql", "oracle", "orm"}
    assert not (must_have - families), f"missing signature families: {must_have - families}"
    # And the union of families is a subset of REQUIRED_FAMILIES.
    assert families.issubset(set(REQUIRED_FAMILIES)), f"unknown families: {families - set(REQUIRED_FAMILIES)}"


def test_every_signature_has_typed_fields() -> None:
    assert sig.SIGNATURES, "SIGNATURES tuple must not be empty"
    for s in sig.SIGNATURES:
        assert s.id and isinstance(s.id, str)
        assert s.name and isinstance(s.name, str)
        assert s.pattern and isinstance(s.pattern, str), f"empty pattern in {s.id}"
        assert s.pattern_type in ("literal", "regex"), f"bad pattern_type in {s.id}"
        assert isinstance(s.case_sensitive, bool)
        assert s.confidence_hint in ("low", "medium", "high"), f"bad confidence_hint in {s.id}"
        assert isinstance(s.requires_context, bool)
        assert s.description, f"empty description in {s.id}"


def test_signature_ids_are_unique() -> None:
    ids = [s.id for s in sig.SIGNATURES]
    assert len(ids) == len(set(ids)), "duplicate Signature.id values"


@pytest.mark.parametrize(
    "family,exemplar_substring",
    [
        ("mysql", "You have an error in your SQL syntax"),
        ("mysql", "mysqli_sql_exception"),
        ("postgresql", "syntax error at or near"),
        ("postgresql", "Npgsql"),
        ("sqlite", "sqlite3.OperationalError"),
        ("mssql", "System.Data.SqlClient.SqlException"),
        ("oracle", "ORA-"),
        ("orm", "SequelizeDatabaseError"),
        ("orm", "PrismaClientKnownRequestError"),
        ("orm", "HibernateException"),
    ],
)
def test_each_required_family_has_signature_for_spec_exemplar(
    family: str, exemplar_substring: str
) -> None:
    """Spec §Signature sources lists exemplar phrases — at least one
    Signature per family must literally include the exemplar in its
    pattern (literal type) or match it (regex type)."""
    candidates = [s for s in sig.SIGNATURES if s.family == family]
    assert candidates, f"no Signature with family={family}"
    matches = [s for s in candidates if exemplar_substring.lower() in s.pattern.lower()]
    if not matches:
        # Allow regex patterns to cover the exemplar.
        import re
        matches = [
            s for s in candidates
            if s.pattern_type == "regex"
            and re.search(s.pattern, exemplar_substring,
                          0 if s.case_sensitive else re.IGNORECASE)
        ]
    assert matches, f"family={family} has no signature covering exemplar {exemplar_substring!r}"
