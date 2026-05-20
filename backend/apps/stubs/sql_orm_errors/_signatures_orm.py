"""ORM Signature rows for stub 1.19 (sequelize / prisma / typeorm /
activerecord / doctrine / hibernate / jdbc).

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/19-sql-orm-errors.md
"""
from __future__ import annotations

from .signatures import Signature


ORM_SIGNATURES: tuple[Signature, ...] = (
    Signature(
        id="orm.sequelize_database",
        family="orm",
        name="Sequelize DatabaseError",
        pattern=r"SequelizeDatabaseError",
        pattern_type="literal",
        case_sensitive=True,
        confidence_hint="high",
        requires_context=False,
        description="Sequelize ORM DatabaseError class.",
    ),
    Signature(
        id="orm.prisma_known_request",
        family="orm",
        name="Prisma KnownRequestError",
        pattern=r"PrismaClientKnownRequestError",
        pattern_type="literal",
        case_sensitive=True,
        confidence_hint="high",
        requires_context=False,
        description="Prisma ORM client known-request-error class.",
    ),
    Signature(
        id="orm.typeorm",
        family="orm",
        name="TypeORM error",
        pattern=r"\bTypeORMError\b|\bQueryFailedError\b",
        pattern_type="regex",
        case_sensitive=True,
        confidence_hint="high",
        requires_context=False,
        description="TypeORM error classes (TypeORMError, QueryFailedError).",
    ),
    Signature(
        id="orm.activerecord_statement_invalid",
        family="orm",
        name="ActiveRecord StatementInvalid",
        pattern=r"ActiveRecord::StatementInvalid",
        pattern_type="literal",
        case_sensitive=True,
        confidence_hint="high",
        requires_context=False,
        description="Rails ActiveRecord ORM SQL-statement-invalid exception.",
    ),
    Signature(
        id="orm.doctrine",
        family="orm",
        name="Doctrine\\DBAL exception",
        pattern=r"Doctrine\\DBAL",
        pattern_type="literal",
        case_sensitive=True,
        confidence_hint="high",
        requires_context=False,
        description="PHP Doctrine DBAL exception namespace.",
    ),
    Signature(
        id="orm.hibernate",
        family="orm",
        name="HibernateException",
        pattern=r"HibernateException",
        pattern_type="literal",
        case_sensitive=True,
        confidence_hint="high",
        requires_context=False,
        description="Java Hibernate ORM exception class.",
    ),
    Signature(
        id="orm.jdbc",
        family="orm",
        name="JDBCException",
        pattern=r"JDBCException",
        pattern_type="literal",
        case_sensitive=True,
        confidence_hint="high",
        requires_context=False,
        description="Java JDBC driver exception class.",
    ),
)
