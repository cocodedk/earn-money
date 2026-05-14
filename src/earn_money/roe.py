"""Per-program Rules of Engagement.

`roe.md` lives alongside `scope.md` in each `programs/<platform>/<slug>/`.
It declares *technique-level* authority for that program: DoS, destructive
payloads, social engineering, PII handling, max request rate, named test
environments, named test accounts. Loaded at runtime by active-probing
runners; never written to the DB.

`CLAUDE.md` is the conservative *floor* for any field a program leaves
unspecified. `default_roe()` returns that floor.
"""

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


class InvalidRoE(Exception):
    """Raised when roe.md is malformed or carries an out-of-range value."""


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

    def manifest_payload(self) -> dict[str, Any]:
        """Audit-trail subset for embedding in a runner's `manifest.json`.

        Omits free-text and list fields — only the technique-level
        authority flags + rate cap, which is what a post-run reviewer
        needs to confirm the probe ran under the right authority.
        """
        return {
            "dos_authorized": self.dos_authorized,
            "destructive_payloads_authorized": self.destructive_payloads_authorized,
            "social_engineering_authorized": self.social_engineering_authorized,
            "pii_handling": self.pii_handling,
            "max_requests_per_second": self.max_requests_per_second,
        }


def default_roe() -> RoE:
    """Conservative floor matching CLAUDE.md's repo-wide invariants.

    Returns the shared `DEFAULT_ROE` singleton — `RoE` is frozen, so a
    single instance is safe to share across callers.
    """
    return DEFAULT_ROE


DEFAULT_ROE = RoE(
    dos_authorized=False,
    destructive_payloads_authorized=False,
    social_engineering_authorized=False,
    pii_handling="one_redacted_screenshot",
    max_requests_per_second=10,
    authorized_test_environments=(),
    authorized_test_accounts=(),
    special_notes="",
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
            meta.get(
                "destructive_payloads_authorized",
                floor.destructive_payloads_authorized,
            ),
            "destructive_payloads_authorized",
        ),
        social_engineering_authorized=_bool(
            meta.get(
                "social_engineering_authorized",
                floor.social_engineering_authorized,
            ),
            "social_engineering_authorized",
        ),
        pii_handling=pii,
        max_requests_per_second=_positive_int(
            meta.get("max_requests_per_second", floor.max_requests_per_second),
            "max_requests_per_second",
        ),
        authorized_test_environments=_str_list(
            meta.get("authorized_test_environments", []),
            "authorized_test_environments",
        ),
        authorized_test_accounts=_str_list(
            meta.get("authorized_test_accounts", []),
            "authorized_test_accounts",
        ),
        special_notes=str(meta.get("special_notes", floor.special_notes)),
    )


__all__ = [
    "DEFAULT_ROE",
    "InvalidRoE",
    "PiiHandling",
    "RoE",
    "default_roe",
    "read_roe",
]
