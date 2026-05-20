"""Stub-local type aliases for `well_known_paths`.

Family Literal pins the six absorbed-spec families. Signature
NamedTuple matches the cookbook's typed-shape contract.

Spec sources: 1.20-1.25.
"""
from __future__ import annotations

from typing import Literal, NamedTuple

from .._shared.types import Confidence


Family = Literal[
    "env", "git", "config_files", "logs", "backup_archives", "db_dumps",
]
PatternType = Literal["literal", "regex", "magic_bytes"]


class Signature(NamedTuple):
    id: str
    family: Family
    pattern: str
    pattern_type: PatternType
    case_sensitive: bool
    confidence_hint: Confidence
    description: str
