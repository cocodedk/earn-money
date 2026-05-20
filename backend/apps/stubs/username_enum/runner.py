"""Stub 2.1 runner — username enumeration.

Phase 2 canary. Demonstrates the full active-auth-probe pattern that
remaining Phase 2 stubs follow:

1. `@guarded_runner("2.1")` handles scope + RECON_ENABLED + FROZEN
   + rate-limit at the Phase 1 layer.
2. This module adds the Phase 2 layer: RoE knob check
   (`allow_active_login_probes`), probe-budget setup, form
   discovery, ProbePair construction, submit + normalize + diff,
   Finding emission.

Slice 02 chunk 1 (this commit): runner skeleton + RoE gate.
The fetcher/submit/diff/finding chain lands in subsequent chunks
so each chunk stays /simplify-reviewable.
"""
from __future__ import annotations

from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.auth.safety import RefusalReason, record_refusal

from ..runners import guarded_runner


@guarded_runner("2.1")
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:
    target = target_run.target
    program = _resolve_program(target)

    if not program.roe.allow_active_login_probes:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id="2.1",
            reason=RefusalReason.ROE_DISABLED,
            details={"knob": "allow_active_login_probes"},
        )
        return

    # Slice 02 chunks 2+ — form discovery + probe + normalize + diff
    # land here. The skeleton intentionally returns silently when RoE
    # permits so the test suite can assert "no refusal event".
    return


def _resolve_program(target):
    """Re-resolve the Program from the registry. `@guarded_runner` did
    this already, but the wrapper doesn't pass it through; we re-resolve
    so the RoE check has the canonical RoE object."""
    from apps.programs.loader import get_registry
    from apps.programs.preflight import host_from_url
    return get_registry().find_for_host(host_from_url(target.base_url))
