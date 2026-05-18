"""Per-program Rules of Engagement — technique-level authority from roe.md."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, get_args

import frontmatter
import yaml

PiiHandling = Literal[
    "one_redacted_screenshot",
    "synthetic_data_only",
    "authorized_per_roe",
]
_ALLOWED_PII: frozenset[str] = frozenset(get_args(PiiHandling))

# Opt-in nuclei template directories beyond the default approved set.
# Any value NOT in this set raises InvalidRoE when read from roe.md.
EXTRA_ALLOWED_NUCLEI_DIRS: frozenset[str] = frozenset({
    "http/vulnerabilities",
    "http/injection",
    "http/xss",
})


class InvalidRoE(Exception):
    """Malformed or out-of-range roe.md value."""


@dataclass(frozen=True)
class RoE:
    dos_authorized: bool
    destructive_payloads_authorized: bool
    social_engineering_authorized: bool
    pii_handling: PiiHandling
    max_requests_per_second: int
    authorized_test_environments: tuple[str, ...]
    authorized_test_accounts: tuple[str, ...]
    special_notes: str = ""
    extra_nuclei_dirs: tuple[str, ...] = ()
    auth_testing_authorized: bool = False
    sqli_time_based: bool = False
    mutation_testing_authorized: bool = False
    auth_lockout_budget: int = 0
    injection_testing_authorized: bool = False

    def manifest_payload(self) -> dict[str, Any]:
        """Audit-trail subset for embedding in a runner's `manifest.json`."""
        return {
            "dos_authorized": self.dos_authorized,
            "destructive_payloads_authorized": self.destructive_payloads_authorized,
            "social_engineering_authorized": self.social_engineering_authorized,
            "pii_handling": self.pii_handling,
            "max_requests_per_second": self.max_requests_per_second,
            "authorized_test_environments": list(self.authorized_test_environments),
            "authorized_test_accounts": list(self.authorized_test_accounts),
            "extra_nuclei_dirs": list(self.extra_nuclei_dirs),
            "auth_testing_authorized": self.auth_testing_authorized,
            "sqli_time_based": self.sqli_time_based,
            "mutation_testing_authorized": self.mutation_testing_authorized,
            "auth_lockout_budget": self.auth_lockout_budget,
            "injection_testing_authorized": self.injection_testing_authorized,
        }


def default_roe() -> RoE:
    """Conservative floor — returns the shared DEFAULT_ROE singleton."""
    return DEFAULT_ROE


DEFAULT_ROE = RoE(
    dos_authorized=False,
    destructive_payloads_authorized=False,
    social_engineering_authorized=False,
    pii_handling="one_redacted_screenshot",
    max_requests_per_second=10,
    authorized_test_environments=(),
    authorized_test_accounts=(),
)


def _bool(value: object, key: str) -> bool:
    if not isinstance(value, bool):
        raise InvalidRoE(f"{key}: must be a boolean, got {type(value).__name__}")
    return value


def _positive_int(value: object, key: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise InvalidRoE(f"{key}: must be a positive integer, got {value!r}")
    return value


def _str_list(value: object, key: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise InvalidRoE(f"{key}: must be a list of strings")
    return tuple(value)


def _non_negative_int(value: object, key: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise InvalidRoE(f"{key}: must be a non-negative integer, got {value!r}")
    return value


def _nuclei_dirs(value: object, key: str) -> tuple[str, ...]:
    dirs = _str_list(value, key)
    bad = frozenset(dirs) - EXTRA_ALLOWED_NUCLEI_DIRS
    if bad:
        raise InvalidRoE(
            f"{key}: unknown dirs {sorted(bad)}; allowed: {sorted(EXTRA_ALLOWED_NUCLEI_DIRS)}"
        )
    return dirs


def read_roe(path: Path) -> RoE:
    """Parse `roe.md` (YAML frontmatter + free markdown body) into an `RoE`.

    A missing file returns `default_roe()` — fresh programs start at the
    floor. Any malformed input raises `InvalidRoE` with the offending key.
    """
    if not path.exists():
        return DEFAULT_ROE

    try:
        post = frontmatter.load(path)
    except yaml.YAMLError as exc:
        raise InvalidRoE(f"{path}: malformed YAML: {exc}") from exc

    meta = post.metadata or {}
    floor = DEFAULT_ROE

    pii = meta.get("pii_handling", floor.pii_handling)
    if pii not in _ALLOWED_PII:
        raise InvalidRoE(
            f"pii_handling: must be one of {sorted(_ALLOWED_PII)}, got {pii!r}"
        )

    return RoE(
        dos_authorized=_bool(
            meta.get("dos_authorized", floor.dos_authorized), "dos_authorized"
        ),
        destructive_payloads_authorized=_bool(
            meta.get("destructive_payloads_authorized", floor.destructive_payloads_authorized),
            "destructive_payloads_authorized",
        ),
        social_engineering_authorized=_bool(
            meta.get("social_engineering_authorized", floor.social_engineering_authorized),
            "social_engineering_authorized",
        ),
        pii_handling=pii,
        max_requests_per_second=_positive_int(
            meta.get("max_requests_per_second", floor.max_requests_per_second),
            "max_requests_per_second",
        ),
        authorized_test_environments=_str_list(
            meta.get("authorized_test_environments", []), "authorized_test_environments",
        ),
        authorized_test_accounts=_str_list(
            meta.get("authorized_test_accounts", []), "authorized_test_accounts",
        ),
        special_notes=str(meta.get("special_notes", floor.special_notes)),
        extra_nuclei_dirs=_nuclei_dirs(
            meta.get("extra_nuclei_dirs", []), "extra_nuclei_dirs",
        ),
        auth_testing_authorized=_bool(
            meta.get("auth_testing_authorized", floor.auth_testing_authorized),
            "auth_testing_authorized",
        ),
        sqli_time_based=_bool(
            meta.get("sqli_time_based", floor.sqli_time_based), "sqli_time_based",
        ),
        mutation_testing_authorized=_bool(
            meta.get("mutation_testing_authorized", floor.mutation_testing_authorized),
            "mutation_testing_authorized",
        ),
        auth_lockout_budget=_non_negative_int(
            meta.get("auth_lockout_budget", floor.auth_lockout_budget), "auth_lockout_budget",
        ),
        injection_testing_authorized=_bool(
            meta.get("injection_testing_authorized", floor.injection_testing_authorized),
            "injection_testing_authorized",
        ),
    )


__all__ = [
    "DEFAULT_ROE",
    "EXTRA_ALLOWED_NUCLEI_DIRS",
    "InvalidRoE",
    "PiiHandling",
    "RoE",
    "default_roe",
    "read_roe",
]
