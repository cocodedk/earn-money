"""Stub 1.19 runner — registration shell.

Slice 19-B ships the `@register("1.19")` decorator + signature so the
runner is dispatchable by the worker (so registration tests pass).
The body is stubbed; slice 19-C wires fetcher → classifier → redaction
→ persistence per the spec.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/19-sql-orm-errors.md
"""
from __future__ import annotations

from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs.runners import register


@register("1.19")
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:  # pragma: no cover — slice 19-C wires this
    """Stub body — slice 19-C ships the real implementation."""
    raise NotImplementedError("stub 1.19 runner body lands in slice 19-C")
