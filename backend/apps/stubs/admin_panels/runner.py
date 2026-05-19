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

from apps.evidence.models import Evidence, EvidenceSource
from apps.findings.models import Finding, FindingStatus, Severity
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget

from .._shared.hashing import body_hash
from .._shared.url import origin
from ..runners import register
from .candidates import CANDIDATE_PATHS
from .fetcher import fetch_evidence
from .signals import (
    has_admin_panel_marker,
    has_login_form,
    is_auth_status,
    is_ok_status,
)


_FINDING_SOURCE = "admin_panels"
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
    bundle = fetch_evidence(target.base_url)
    if bundle["baseline"] is None:
        return

    probes = bundle["probes"]
    soft_404 = _soft_404_profile(probes)
    hits = _evaluate_probes(probes, soft_404, target.base_url)
    if not hits:
        return

    evidences, findings = _build_rows(
        hits=hits, scan_run=scan_run, target=target,
    )

    with transaction.atomic():
        Evidence.objects.bulk_create(evidences)
        Finding.objects.bulk_create(findings)


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
    # Protocol-relative `//host/path` inherits the base URL's scheme but
    # specifies a (possibly different) host. Normalise to absolute form
    # before the origin check, otherwise `//attacker.example/admin`
    # would slip through as "no scheme → treat as relative" and the
    # cross-origin filter wouldn't fire.
    if location.startswith("//"):
        location = f"{urlsplit(base_url).scheme}:{location}"
    if "://" in location and origin(location) != origin(base_url):
        return False
    path = (
        urlsplit(location).path if "://" in location else location
    ).lower()
    return any(term in path for term in _ADMIN_PATH_TERMS)


def _build_rows(
    hits: list[tuple[str, dict, str, str]],
    scan_run: ScanRun,
    target: ScanTarget,
) -> tuple[list[Evidence], list[Finding]]:
    evidences: list[Evidence] = []
    findings: list[Finding] = []

    for path, probe, confidence, signal_kind in hits:
        url = urljoin(target.base_url, path)
        evidence = Evidence(
            scan_run=scan_run,
            target=target,
            source=EvidenceSource.PATH,
            url=url,
            method="GET",
            field=signal_kind,
            matched_value=path,
            raw_excerpt=f"{signal_kind}: {path} (status {probe['status']})"[:200],
            data={
                "path": path,
                "status": probe["status"],
                "signal_kind": signal_kind,
                "location": probe.get("location"),
            },
        )
        evidences.append(evidence)
        findings.append(
            Finding(
                scan_run=scan_run,
                target=target,
                stub_slug=scan_run.stub_slug,
                title=f"Admin panel exposure: {path} ({signal_kind})",
                category=signal_kind,
                severity=Severity.INFO,
                confidence=confidence,
                status=FindingStatus.CANDIDATE,
                data={
                    "finding_type": "exposed_admin_panel",
                    "path": path,
                    "status": probe["status"],
                    "signal_kind": signal_kind,
                    "evidence_ids": [str(evidence.id)],
                    "source": _FINDING_SOURCE,
                },
            )
        )

    return evidences, findings
