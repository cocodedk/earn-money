"""Shared helpers for stub 1.6 runner tests."""
from __future__ import annotations

from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._test_factories import seed_target_run


def seed_for_1_6() -> tuple[ScanRun, ScanTargetRun]:
    return seed_target_run(stub_slug="1.6", host="x.example")


def make_baseline(body: str = "welcome") -> dict:
    return {"status": 200, "body": body, "url": "https://x.example/"}


def make_probe(body: str = "", status: int = 200) -> dict:
    return {"status": status, "body": body, "url": ""}


def make_bundle(
    baseline: dict | None = None,
    probes: dict[str, dict] | None = None,
) -> dict:
    return {
        "baseline": baseline if baseline is not None else make_baseline(),
        "probes": probes or {},
    }


def make_nonce_bundle(
    nonce_body: str = "not found",
    nonce_status: int = 404,
    probes: dict[str, dict] | None = None,
) -> dict:
    base_probes = {
        "/.well-known/scanner_nonexistent_aaaaaaaa": make_probe(
            nonce_body, nonce_status
        ),
        "/scanner_nonexistent_bbbbbbbb": make_probe(nonce_body, nonce_status),
    }
    if probes:
        base_probes.update(probes)
    return make_bundle(probes=base_probes)
