"""Stub 1.9 runner — placeholder. Real implementation lands in
subsequent commits."""
from __future__ import annotations

from apps.scans.models import ScanRun, ScanTargetRun

from ..runners import register


@register("1.9")
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:  # pragma: no cover
    """Placeholder — real implementation lands in next commit."""
    return None
