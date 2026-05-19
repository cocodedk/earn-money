"""Tests for the shared cookbook Literal aliases.

These are type-only aliases (erased at runtime), but pin the
membership set explicitly so a downstream rename / typo wouldn't
quietly accept a new value at runtime.
"""
from __future__ import annotations

import unittest
from typing import get_args

from ..types import Confidence


class ConfidenceTests(unittest.TestCase):
    def test_membership_matches_cookbook_vocabulary(self) -> None:
        assert set(get_args(Confidence)) == {"low", "medium", "high"}

    def test_ordered_lowest_to_highest(self) -> None:
        # `apps.findings.confidence.CONFIDENCE_RANK` keys are ordered
        # low < medium < high. The Literal alias matches that order
        # so iteration is deterministic across the codebase.
        assert get_args(Confidence) == ("low", "medium", "high")
