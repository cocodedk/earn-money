"""Backend-wide pytest fixtures.

Autouse fixture sets up scope-enforcement infrastructure so every test
that creates a ScanRun via the API serializer gets a passing pre-flight
by default. Tests that need to exercise the refusal cases override
PROGRAMS_ROOT / RECON_ENABLED_PATH locally via `override_settings`.

The default coverage spans every hostname that existing scan-run tests
already use (`x.example`, `*.cocode.dk`, etc.), so this fixture is
additive: existing tests keep working unchanged, while new tests can
opt into the strict modes by pointing settings at an empty fixture
dir.
"""
from __future__ import annotations

import pytest
from django.conf import settings
from django.test.utils import override_settings


_TEST_PROGRAM_SLUG = "__tests_default__"


@pytest.fixture(autouse=True)
def _scope_enforcement_test_defaults(tmp_path_factory):
    """Materialise a default `tests/__tests_default__` program + a
    RECON_ENABLED flag-file at temp paths, then override Django
    settings to point at them for the duration of the test.
    """
    root = tmp_path_factory.mktemp("scope_enforcement_defaults")
    programs_root = root / "programs"
    program_dir = programs_root / "tests" / _TEST_PROGRAM_SLUG
    program_dir.mkdir(parents=True)
    (program_dir / "scope.md").write_text(
        f"""---
platform: tests
slug: {_TEST_PROGRAM_SLUG}
policy: rate-limited-OK
in_scope:
- "*.example"
- "*.example.com"
- "*.cocode.dk"
- "*.invalid"
- "*.test"
- "x.example"
out_of_scope: []
---
# Default-scope program for the backend test-suite.
""",
        encoding="utf-8",
    )
    (program_dir / "roe.md").write_text(
        """---
max_requests_per_second: 100
---
""",
        encoding="utf-8",
    )
    flag = root / "RECON_ENABLED"
    flag.write_text("test-mode", encoding="utf-8")

    # Reset the lazy registry so the override takes effect.
    from apps.programs import loader as _loader
    _loader._default_registry = None

    with override_settings(PROGRAMS_ROOT=programs_root, RECON_ENABLED_PATH=flag):
        yield

    _loader._default_registry = None
