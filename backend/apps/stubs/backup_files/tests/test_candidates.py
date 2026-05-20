"""Candidate-list contract for stub 1.7."""
from __future__ import annotations

import unittest

from ..candidates import CANDIDATES


ALLOWED_SOURCE_KINDS = {
    "archive",
    "db_dump",
    "secret_file",
    "config_file",
    "vcs_leak",
    "os_metadata",
}


class CandidatesShapeTests(unittest.TestCase):
    def test_each_entry_is_path_kind_pair(self) -> None:
        for entry in CANDIDATES:
            assert len(entry) == 2
            path, kind = entry
            assert path.startswith("/")
            assert kind in ALLOWED_SOURCE_KINDS

    def test_paths_are_unique(self) -> None:
        paths = [p for p, _ in CANDIDATES]
        assert len(paths) == len(set(paths))

    def test_includes_high_signal_categories(self) -> None:
        kinds = {kind for _, kind in CANDIDATES}
        # Every category MUST have at least one representative.
        assert ALLOWED_SOURCE_KINDS == kinds
