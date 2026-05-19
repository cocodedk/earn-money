"""Shared helpers for stub 1.8 runner tests."""
from __future__ import annotations

from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._test_factories import seed_target_run


def seed_for_1_8() -> tuple[ScanRun, ScanTargetRun]:
    return seed_target_run(stub_slug="1.8", host="x.example")


def make_baseline(body: str = "welcome") -> dict:
    return {
        "status": 200, "body": body, "url": "https://x.example/",
        "location": None,
    }


def make_probe(
    body: str = "", status: int = 200, location: str | None = None,
) -> dict:
    return {"status": status, "body": body, "url": "", "location": location}


def make_nonce_bundle(
    nonce_body: str = "not found",
    nonce_status: int = 404,
    probes: dict[str, dict] | None = None,
    baseline: dict | None = None,
) -> dict:
    base_probes = {
        "/scanner-baseline-aaaaaaaa": make_probe(nonce_body, nonce_status),
        "/scanner-baseline-bbbbbbbb": make_probe(nonce_body, nonce_status),
    }
    base_probes.update(probes or {})
    return {
        "baseline": baseline if baseline is not None else make_baseline(),
        "probes": base_probes,
    }
