"""Signature table for stub 1.19 sql_orm_errors.

Per spec §Signature sources + §Persistence. Each `Signature` row is a
typed NamedTuple matching the spec's `SqlOrmErrorSignature` shape with:

- `family`: spec-pinned DB/ORM family (mysql / postgresql / sqlite /
  mssql / oracle / mariadb / orm / driver / generic_sql / other).
- `pattern` + `pattern_type` + `case_sensitive`: the textual signal.
- `confidence_hint`: spec §Classification ladder hint
  (strong → high; framework_hint + error_status → medium; weak → low).
- `requires_context`: True means this pattern alone is not enough;
  the matcher must also see SQL fragment, driver name, stack frame,
  or table/column name. False = pattern is strong on its own.

Order matters for the matcher: more-specific families come first so
`postgresql` beats `generic_sql` on `syntax error at or near`, etc.
The combined SIGNATURES tuple below is consumed by `signals.py`.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/19-sql-orm-errors.md
"""
from __future__ import annotations

from typing import Literal, NamedTuple


Family = Literal[
    "mysql", "postgresql", "sqlite", "mssql", "oracle",
    "mariadb", "orm", "driver", "generic_sql", "other",
]
Confidence = Literal["low", "medium", "high"]
PatternType = Literal["literal", "regex"]


class Signature(NamedTuple):
    id: str
    family: Family
    name: str
    pattern: str
    pattern_type: PatternType
    case_sensitive: bool
    confidence_hint: Confidence
    requires_context: bool
    description: str


from ._signatures_relational import RELATIONAL_SIGNATURES  # noqa: E402
from ._signatures_orm import ORM_SIGNATURES  # noqa: E402
from ._signatures_misc import MISC_SIGNATURES  # noqa: E402


SIGNATURES: tuple[Signature, ...] = (
    *RELATIONAL_SIGNATURES,
    *ORM_SIGNATURES,
    *MISC_SIGNATURES,
)
