"""Canonical finding schema shared with clawpwn.

Version tracked by `CANONICAL_FINDING_VERSION`. Bump together with any
field change so either side can assert on it when wiring cross-repo data.

Tag namespacing convention:
  earn-money tags: ``em:<key>=<value>``  e.g. ``em:program=algolia``
  clawpwn tags:    ``clw:<key>=<value>`` e.g. ``clw:project=myproject``

The ``evidence_block`` field is the output of
``wrap_evidence(...).to_block()`` from ``earn_money.agent.evidence``.
It is optional because offline / taxonomy-derived findings may not have
a live HTTP response to attach.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CANONICAL_FINDING_VERSION: str = "1"


@dataclass(frozen=True, slots=True)
class CanonicalFinding:
    title: str
    severity: Literal["info", "low", "medium", "high", "critical"]
    confidence: Literal["low", "medium", "high"]
    affected_asset: str          # domain / URL / IP / package — required
    attack_type: str             # taxonomy key, e.g. "sql-injection"
    description: str
    source_tool: str             # e.g. "nuclei", "httpx-probe"
    cwe: str | None              # e.g. "CWE-89"
    owasp: str | None            # e.g. "A03:2021"
    remediation: str | None
    references: tuple[str, ...]
    evidence_block: str | None   # wrap_evidence(...).to_block() or None
    url: str | None              # HTTP-specific, optional
    tags: tuple[str, ...]        # namespaced: "em:program=algolia", etc.


class FindingNormalizer:
    """Protocol for tool-specific raw-output → CanonicalFinding converters."""

    tool: str

    def normalize(self, raw: object) -> CanonicalFinding | None:
        """Return a CanonicalFinding or None if raw is not a known finding."""
        raise NotImplementedError
