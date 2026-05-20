"""Family contract for `well_known_paths`.

Each of the six absorbed-spec families (env / git / config_files /
logs / backup_archives / db_dumps) exposes:
  * a non-empty candidate-path tuple (≥10 paths per spec audit)
  * a non-empty signature set
  * a typed severity hint

Spec sources: 1.20-1.25.
"""
from __future__ import annotations

from apps.findings.models import Severity
from apps.stubs.well_known_paths import families


REQUIRED_FAMILIES = (
    "env", "git", "config_files", "logs", "backup_archives", "db_dumps",
)


def test_six_families_present() -> None:
    seen = {fam.family for fam in families.FAMILIES}
    assert seen == set(REQUIRED_FAMILIES)


def test_each_family_has_candidate_paths() -> None:
    for fam in families.FAMILIES:
        assert len(fam.candidate_paths) >= 10, (
            f"family {fam.family} has only {len(fam.candidate_paths)} paths; "
            f"spec audit requires ≥10"
        )
        # All paths must be absolute (start with "/").
        assert all(p.startswith("/") for p in fam.candidate_paths)


def test_each_family_has_signatures() -> None:
    for fam in families.FAMILIES:
        assert len(fam.signatures) >= 1, f"family {fam.family} has no signatures"
        for sig in fam.signatures:
            assert sig.family == fam.family, (
                f"signature {sig.id} family={sig.family!r} bound under {fam.family!r}"
            )
            assert sig.pattern, f"signature {sig.id} has empty pattern"
            assert sig.pattern_type in ("literal", "regex", "magic_bytes")
            assert sig.confidence_hint in ("low", "medium", "high")


def test_severity_hints_within_spec_cap() -> None:
    """Spec §Severity guidance: cap at MEDIUM for this check."""
    allowed = {Severity.INFO, Severity.LOW, Severity.MEDIUM}
    for fam in families.FAMILIES:
        assert fam.severity_hint in allowed, (
            f"family {fam.family} severity={fam.severity_hint} exceeds spec cap"
        )


def test_get_family_roundtrips() -> None:
    fam = families.get_family("env")
    assert fam.family == "env"
    assert fam.severity_hint == Severity.MEDIUM
    # Look up a non-first family too, to exercise the iteration past
    # earlier rows.
    db = families.get_family("db_dumps")
    assert db.family == "db_dumps"
