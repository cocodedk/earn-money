"""Stub `well_known_paths` runner — registration shell.

Slice WKP-A ships the `@register("1.20")` decorator + signature so the
runner is dispatchable by the worker (registration test passes).
Real body wires soft-404 prelude → per-family iteration → HEAD-first
fetcher → classify → redact → persist in slice WKP-C.

One @register call owns specs 1.20-1.25 per the 1.10→1.18 precedent
(codex-blessed direction 2026-05-20).

Spec sources: 1.20 / 1.21 / 1.22 / 1.23 / 1.24 / 1.25.
"""
from __future__ import annotations

from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs.runners import register


@register("1.20")
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:  # pragma: no cover — slice WKP-C wires this
    """Stub body — slice WKP-C ships the real implementation."""
    raise NotImplementedError(
        "well_known_paths runner body lands in slice WKP-C"
    )
