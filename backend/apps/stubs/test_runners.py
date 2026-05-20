"""Tests for the stub runner registry — written BEFORE the registry."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from .runners import (
    _clear_for_testing,
    get,
    register,
    registered_slugs,
)


class RegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        _clear_for_testing()

    def tearDown(self) -> None:
        _clear_for_testing()

    def test_register_then_get_roundtrips(self) -> None:
        runner = lambda r, t: None  # noqa: E731
        register("1.1")(runner)
        assert get("1.1") is runner

    def test_decorator_returns_the_function(self) -> None:
        @register("1.1")
        def runner(scan_run, target_run):
            return "ran"

        assert runner is get("1.1")
        # Decorator preserves the original function — call works.
        assert runner(MagicMock(), MagicMock()) == "ran"

    def test_unknown_slug_returns_none(self) -> None:
        assert get("99.99") is None

    def test_re_registering_same_slug_overrides(self) -> None:
        first = lambda r, t: None  # noqa: E731
        second = lambda r, t: None  # noqa: E731
        register("1.1")(first)
        register("1.1")(second)
        assert get("1.1") is second

    def test_registered_slugs_returns_sorted_list(self) -> None:
        register("2.1")(lambda r, t: None)
        register("1.1")(lambda r, t: None)
        register("1.2")(lambda r, t: None)
        assert registered_slugs() == ["1.1", "1.2", "2.1"]

    def test_clear_for_testing_resets(self) -> None:
        register("1.1")(lambda r, t: None)
        assert get("1.1") is not None
        _clear_for_testing()
        assert get("1.1") is None
        assert registered_slugs() == []
