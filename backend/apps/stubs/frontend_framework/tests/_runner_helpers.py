"""Shared helpers for stub 1.3 runner tests.

Underscore prefix marks it test-internal; production code MUST NOT
import this module.
"""
from __future__ import annotations

from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._test_factories import seed_target_run


def seed_for_1_3() -> tuple[ScanRun, ScanTargetRun]:
    return seed_target_run(stub_slug="1.3", host="x.example")


def make_bundle(
    html_body: str = "",
    script_paths: list[str] | None = None,
    asset_bodies: dict[str, str] | None = None,
) -> dict:
    return {
        "html_body": html_body,
        "script_paths": script_paths or [],
        "asset_bodies": asset_bodies or {},
        "url": "https://x.example/",
    }
