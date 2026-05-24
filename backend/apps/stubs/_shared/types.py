"""Shared cookbook vocabulary types for stub classifiers.

The shared schema defines closed string-unions for several fields
(`confidence`, etc.). Django's `TextChoices` already covers
`FindingStatus`, `Severity`, and `EvidenceSource`, so those don't
need Literal aliases here. `confidence` is the field that's stored
in the database as a free-form CharField — the Literal alias gives
the per-stub `Verdict.confidence` field type-checker enforcement
without coupling to the Django ORM.

Add new shared Literal aliases here only when at least two stubs
share the vocabulary. Stub-specific kinds (e.g. DebugPageKind,
RobotsTxtClassification) stay local to their stub package.
"""
from __future__ import annotations

from typing import Literal


# Cookbook §00-shared-schema "confidence" vocabulary. Used by every
# stub classifier's Verdict.confidence and the runner's Finding.data.
Confidence = Literal["low", "medium", "high"]

# Cookbook §00-shared-schema "status" vocabulary. Used by every stub
# classifier's result/verdict status field.
Status = Literal["candidate", "confirmed", "rejected", "stale"]
