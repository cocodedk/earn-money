"""Shared helpers for stub 1.9 runner tests."""
from __future__ import annotations

from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._test_factories import seed_target_run


def seed_for_1_9() -> tuple[ScanRun, ScanTargetRun]:
    return seed_target_run(stub_slug="1.9", host="x.example")


def make_baseline(body: str = "welcome") -> dict:
    return {
        "status": 200, "body": body, "url": "https://x.example/",
        "headers": {}, "location": None,
    }


def make_probe(
    body: str = "",
    status: int = 200,
    location: str | None = None,
    headers: dict[str, str] | None = None,
) -> dict:
    return {
        "status": status,
        "body": body,
        "url": "",
        "headers": headers or {},
        "location": location,
    }


def make_bundle(
    control_body: str = "not found",
    control_status: int = 404,
    probes: dict[str, dict] | None = None,
    baseline: dict | None = None,
) -> dict:
    base_probes = {
        f"/__scanner_control_not_found_aaaa{n}": make_probe(
            control_body, control_status,
        )
        for n in (1, 2, 3)
    }
    base_probes.update(probes or {})
    return {
        "baseline": baseline if baseline is not None else make_baseline(),
        "probes": base_probes,
    }
