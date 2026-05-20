"""Family enum + per-family candidate-path/signature/severity binding
for stub `well_known_paths`.

One stub absorbs cookbook specs 1.20-1.25 per the 1.10→1.18 precedent.
The runner iterates every Family on each target; `Finding.category` is
`well_known_paths.<family>` so per-family taxonomy stays distinct.

Spec sources: 1.20 / 1.21 / 1.22 / 1.23 / 1.24 / 1.25.
"""
from __future__ import annotations

from typing import NamedTuple

from apps.findings.models import Severity

from ._paths import (
    ARCHIVE_PATHS,
    CONFIG_PATHS,
    DB_DUMP_PATHS,
    ENV_PATHS,
    GIT_PATHS,
    LOG_PATHS,
)
from ._signatures import SIGNATURES_BY_FAMILY
from ._types import Family, Signature


class FamilySpec(NamedTuple):
    """All per-family contract bound in one row."""
    family: Family
    candidate_paths: tuple[str, ...]
    signatures: tuple[Signature, ...]
    severity_hint: str  # Severity.{HIGH|MEDIUM|LOW|INFO} value


# Severity hints per spec §Severity guidance (capped at medium for
# this check; never high/critical from disclosure alone).
FAMILIES: tuple[FamilySpec, ...] = (
    FamilySpec(
        family="env",
        candidate_paths=ENV_PATHS,
        signatures=SIGNATURES_BY_FAMILY["env"],
        severity_hint=Severity.MEDIUM,
    ),
    FamilySpec(
        family="git",
        candidate_paths=GIT_PATHS,
        signatures=SIGNATURES_BY_FAMILY["git"],
        severity_hint=Severity.MEDIUM,
    ),
    FamilySpec(
        family="config_files",
        candidate_paths=CONFIG_PATHS,
        signatures=SIGNATURES_BY_FAMILY["config_files"],
        severity_hint=Severity.LOW,
    ),
    FamilySpec(
        family="logs",
        candidate_paths=LOG_PATHS,
        signatures=SIGNATURES_BY_FAMILY["logs"],
        severity_hint=Severity.LOW,
    ),
    FamilySpec(
        family="backup_archives",
        candidate_paths=ARCHIVE_PATHS,
        signatures=SIGNATURES_BY_FAMILY["backup_archives"],
        severity_hint=Severity.MEDIUM,
    ),
    FamilySpec(
        family="db_dumps",
        candidate_paths=DB_DUMP_PATHS,
        signatures=SIGNATURES_BY_FAMILY["db_dumps"],
        severity_hint=Severity.MEDIUM,
    ),
)


def get_family(name: Family) -> FamilySpec:
    """Look up a FamilySpec by family name."""
    for fam in FAMILIES:
        if fam.family == name:
            return fam
    raise KeyError(f"unknown family: {name}")  # pragma: no cover
