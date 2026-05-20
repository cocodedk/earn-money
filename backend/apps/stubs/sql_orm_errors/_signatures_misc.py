"""Driver / generic / other Signature rows for stub 1.19.

These rows are weaker on their own (most have requires_context=True)
and fall back when no relational/ORM family fires. Includes the
SQLSTATE driver code (high), generic phrases (low), and rare extension
drivers (MongoDB/Neo4j).

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/19-sql-orm-errors.md
"""
from __future__ import annotations

from .signatures import Signature


MISC_SIGNATURES: tuple[Signature, ...] = (
    # --- driver (non-family-specific) ---
    Signature(
        id="driver.pdo_exception",
        family="driver",
        name="PDOException",
        pattern=r"PDOException",
        pattern_type="literal",
        case_sensitive=True,
        confidence_hint="medium",
        requires_context=True,
        description="PHP PDO database-abstraction exception class.",
    ),
    Signature(
        id="driver.sqlstate",
        family="driver",
        name="SQLSTATE code",
        pattern=r"SQLSTATE\[\w{5}\]",
        pattern_type="regex",
        case_sensitive=True,
        confidence_hint="high",
        requires_context=False,
        description="SQL standard SQLSTATE[XXXXX] code disclosure.",
    ),

    # --- generic_sql (weak signals — requires_context=True) ---
    Signature(
        id="generic_sql.database_error",
        family="generic_sql",
        name="Generic 'database error' phrase",
        pattern=r"\bdatabase error\b",
        pattern_type="regex",
        case_sensitive=False,
        confidence_hint="low",
        requires_context=True,
        description="Generic database-error phrase. Weak; requires context.",
    ),
    Signature(
        id="generic_sql.unterminated_string",
        family="generic_sql",
        name="Unterminated quoted string",
        pattern=(
            r"unterminated quoted string"
            r"|unclosed quotation mark"
            r"|quoted string not properly terminated"
        ),
        pattern_type="regex",
        case_sensitive=False,
        confidence_hint="medium",
        requires_context=True,
        description="Cross-DB parser error for unterminated literal.",
    ),

    # --- other (rare/extension drivers) ---
    Signature(
        id="other.mongo_server_error",
        family="other",
        name="MongoServerError",
        pattern=r"MongoServerError|MongooseError",
        pattern_type="regex",
        case_sensitive=True,
        confidence_hint="medium",
        requires_context=True,
        description="MongoDB driver/ODM error class.",
    ),
    Signature(
        id="other.neo4j_syntax",
        family="other",
        name="Neo4j Cypher syntax error",
        pattern=r"Neo\.ClientError\.Statement\.SyntaxError",
        pattern_type="literal",
        case_sensitive=True,
        confidence_hint="high",
        requires_context=False,
        description="Neo4j Cypher Statement SyntaxError code.",
    ),
)
