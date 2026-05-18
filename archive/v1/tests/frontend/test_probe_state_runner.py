"""Run the Node-based frontend test suite from pytest.

If Node is not on PATH, the test is skipped with a clear message.
Otherwise: `node --test <files>` runs each `*.test.mjs` and its exit
code + output drive pass/fail.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_FRONTEND_DIR = Path(__file__).parent


def test_frontend_js_suite() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not on PATH — install Node 18+ to run the JS test suite")
    test_files = sorted(str(p) for p in _FRONTEND_DIR.glob("*.test.mjs"))
    if not test_files:
        pytest.skip("no *.test.mjs files yet")
    result = subprocess.run(
        [node, "--test", *test_files],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
