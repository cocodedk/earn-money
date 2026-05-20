"""Stub 1.8 runner — registered against stub_slug "1.8".

Per spec: build soft-404 profile from 2 nonce probes, then evaluate
each candidate-path probe against:
- Status 401/403: explicit auth gate → high confidence.
- Status 200 + body has login-form OR admin-panel markers → high.
- Status 200, body distinct from soft-404, no body markers → medium.
- Status 302 with same-origin Location to an admin-like path → medium.
- Everything else (404 or soft-404 match): skip.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/08-exposed-admin-panels.md
"""
from __future__ import annotations

from urllib.parse import urljoin, urlsplit

from django.db import transaction

from apps.evidence.models import Evidence
from apps.findings.models import Finding
from apps.findings.bulk import bulk_create_findings
from apps.programs.exceptions import OutOfScope
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.http import resolve_and_guard

from .._shared.hashing import body_hash
from .._shared.url import origin
from ..runners import register
from .candidates import CANDIDATE_PATHS
from .fetcher import fetch_evidence
from .runner_persistence import build_rows
from .signals import (
    has_admin_panel_marker,
    has_login_form,
    is_auth_status,
    is_ok_status,
)


_NONCE_MARKER = "scanner-baseline-"
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}

# Admin-like path terms used to validate a 302 Location target is
# itself an admin route hint.
_ADMIN_PATH_TERMS = (
    "admin", "console", "dashboard", "manage", "panel", "backend",
    "cpanel", "manager", "moderator", "siteadmin", "superadmin",
)


@register("1.8")
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:
    target = target_run.target
    try:
        resolve_and_guard(scan_run, target, stub_id="1.8")
    except OutOfScope:
        return  # event already emitted; halt this stub
    bundle = fetch_evidence(target.base_url)
    if bundle["baseline"] is None:
        return

    probes = bundle["probes"]
    soft_404 = _soft_404_profile(probes)
    hits = _evaluate_probes(probes, soft_404, target.base_url)
    if not hits:
        return

    evidences, findings = build_rows(
        hits=hits, scan_run=scan_run, target=target,
    )

    with transaction.atomic():
        Evidence.objects.bulk_create(evidences)
        bulk_create_findings(findings)


def _soft_404_profile(probes: dict[str, dict]) -> set[str]:
    """Build the soft-404 reference hash set from the nonce probes.

    Per spec §Soft-404: a status-200 candidate is soft-404 only when
    its body fingerprint matches BOTH random missing paths. If the two
    nonces produced the SAME body (the common case — server returns a
    canonical 404 page or SPA shell for every unknown route), the set
    has one entry and candidate-matches-set means matches-both. If the
    nonces produced DIFFERENT bodies (rare; suggests the server's
    not-found response varies), no stable baseline exists — return an
    empty set so no candidate is suppressed by an unreliable profile."""
    nonce_hashes = {
        body_hash(probe["body"])
        for path, probe in probes.items()
        if _NONCE_MARKER in path
    }
    if len(nonce_hashes) != 1:
        return set()
    return nonce_hashes


def _evaluate_probes(
    probes: dict[str, dict],
    soft_404: set[str],
    base_url: str,
) -> list[tuple[str, dict, str, str]]:
    """Return [(path, probe, confidence, signal_kind), ...] for probes
    that look like real admin-panel exposures."""
    hits: list[tuple[str, dict, str, str]] = []
    for path in CANDIDATE_PATHS:
        probe = probes.get(path)
        if probe is None:
            continue
        status = probe["status"]
        if status == 404:
            continue
        evaluation = _evaluate_one(probe, soft_404, base_url)
        if evaluation is None:
            continue
        confidence, signal_kind = evaluation
        hits.append((path, probe, confidence, signal_kind))
    return hits


def _evaluate_one(
    probe: dict, soft_404: set[str], base_url: str
) -> tuple[str, str] | None:
    status = probe["status"]
    body = probe["body"]

    if is_auth_status(status):
        # 401/403 on an admin path IS the find — server is gating it.
        return ("high", "auth_required")

    if status in _REDIRECT_STATUSES:
        location = probe.get("location") or ""
        if _is_same_origin_admin_redirect(location, base_url):
            return ("medium", "redirect_to_admin")
        return None

    if not is_ok_status(status):
        return None

    has_form = has_login_form(body)
    has_panel = has_admin_panel_marker(body)
    soft_match = body_hash(body) in soft_404

    if has_form or has_panel:
        return ("high", "body_markers")
    if not soft_match:
        return ("medium", "distinct_body")
    return None


def _is_same_origin_admin_redirect(location: str, base_url: str) -> bool:
    if not location:
        return False
    # urljoin resolves protocol-relative `//host/path` against base_url so
    # `//attacker.example/admin` can't bypass the same-origin check.
    absolute = urljoin(base_url, location)
    if origin(absolute) != origin(base_url):
        return False
    path = urlsplit(absolute).path.lower()
    return any(term in path for term in _ADMIN_PATH_TERMS)
