"""Stub 1.19 registers under spec ID "1.19" via @register on the runner.

apps.py `ready()` imports the stub package; the package's __init__
imports runner.run; the @register decorator fires.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/19-sql-orm-errors.md
"""
from __future__ import annotations

import importlib

from apps.stubs.runners import get as get_runner


def test_19_is_registered() -> None:
    """Re-import the runner module so `@register("1.19")` fires.

    `apps.stubs.test_runners.RegistryTests` wipes the global registry
    in its setUp/tearDown via `_clear_for_testing()`, so we can't rely
    on `apps.ready()`'s one-time import side-effect. Reloading the
    module is the cheap, ordering-robust way to re-fire the decorator.
    """
    from apps.stubs.sql_orm_errors import runner as runner_module
    importlib.reload(runner_module)
    assert get_runner("1.19") is runner_module.run
