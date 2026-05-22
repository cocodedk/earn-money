"""Smoke tests for `apps.programs.exceptions` — every type instantiates
and inherits from Exception so later slices can catch them.
"""
from __future__ import annotations

import pytest

from apps.programs.exceptions import (
    AmbiguousPolicy,
    AmbiguousProgram,
    InvalidScope,
    ManualOnly,
    OutOfScope,
    ProgramFrozen,
    ReconDisabled,
)


@pytest.mark.parametrize(
    "exc",
    [InvalidScope, OutOfScope, ManualOnly, AmbiguousPolicy,
     AmbiguousProgram, ReconDisabled, ProgramFrozen],
)
def test_inherits_from_exception(exc: type[Exception]) -> None:
    assert issubclass(exc, Exception)
    inst = exc("test")
    assert str(inst) == "test"
