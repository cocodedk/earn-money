"""Stub 2.14 runner — oauth-redirect-uri."""
from __future__ import annotations

import json
import os
import secrets

import httpx

from apps.findings.models import Finding, FindingStatus, Severity
from apps.programs.loader import Program
from apps.programs.rate_limit import acquire_for
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.auth.discovery import fetch_for_discovery
from apps.stubs._shared.auth.events import log_finding_candidate
from apps.stubs._shared.auth.requests import submit_probe
from apps.stubs._shared.auth.safety import RefusalReason, record_refusal
from apps.targets.models import ScanTarget

from ..runners import guarded_runner
from .classify import classify_redirect_response
from .mutate import generate_mutations


_FIXTURE_SECRET_ENV = "FIXTURE_OAUTH_CLIENT_SECRET"
_STUB_ID = "2.14"
_SCANNER_ORIGIN = os.environ.get("SCANNER_REDIRECT_ORIGIN", "https://scanner.invalid")


@guarded_runner("2.14")
def run(
    scan_run: ScanRun, target_run: ScanTargetRun,
    *, program: Program,
) -> None:
    if not program.roe.allow_oauth_probes:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.ROE_DISABLED,
            details={"knob": "allow_oauth_probes"},
        )
        return

    if not program.roe.authorized_test_accounts:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "no_authorized_test_accounts"},
        )
        return

    if not os.environ.get(_FIXTURE_SECRET_ENV):
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.MISSING_SECRET,
            details={"missing_secret": _FIXTURE_SECRET_ENV},
        )
        return

    target = target_run.target
    fixture_url = os.environ.get("FIXTURE_OAUTH_REDIRECT_URI_URL", target.base_url)

    # OIDC discovery
    acquire_for(program)
    oidc_resp = fetch_for_discovery(
        fixture_url + "/.well-known/openid-configuration",
        target=target, program=program,
    )
    if not oidc_resp.ok:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.TRANSPORT_ERROR,
            details={"detail": "oidc_discovery_unreachable"},
        )
        return

    try:
        doc = json.loads(oidc_resp.body)
    except Exception:
        return

    primary_endpoint = doc.get("authorization_endpoint", "")
    auth_endpoints = [
        ep for ep in [primary_endpoint, *doc.get("authorization_endpoint_variants", [])]
        if ep
    ]
    if not auth_endpoints:
        return

    baseline_redirect = os.environ.get(
        "FIXTURE_OAUTH_KNOWN_REDIRECT_URI",
        "https://app.example.test/oauth/callback",
    )
    client_id = os.environ.get("FIXTURE_OAUTH_CLIENT_ID", "test-client")

    mutations = generate_mutations(
        baseline_redirect_uri=baseline_redirect,
        scanner_origin=_SCANNER_ORIGIN,
        max_probes=8,
    )

    first_candidate = None
    for auth_endpoint in auth_endpoints:
        for mutation in mutations:
            acquire_for(program)
            # submit_probe must preserve 3xx responses; do not follow redirects.
            request = httpx.Request(
                "GET", auth_endpoint,
                params={
                    "client_id": client_id,
                    "redirect_uri": mutation.mutated_uri,
                    "response_type": "code",
                    "state": secrets.token_hex(8),
                },
            )
            resp = submit_probe(request)
            if resp is None:
                continue
            classification = classify_redirect_response(resp, _SCANNER_ORIGIN)
            if classification.status == "confirmed":
                _emit_finding_redirect(
                    scan_run=scan_run, target=target,
                    auth_endpoint=auth_endpoint,
                    mutation_class=mutation.mutation_class.value,
                    classification=classification,
                )
                return  # One confirmed finding per target is enough
            if classification.status == "candidate" and first_candidate is None:
                first_candidate = (auth_endpoint, mutation, classification)

    if first_candidate is not None:
        auth_endpoint, mutation, classification = first_candidate
        _emit_finding_redirect(
            scan_run=scan_run, target=target,
            auth_endpoint=auth_endpoint,
            mutation_class=mutation.mutation_class.value,
            classification=classification,
        )


def _emit_finding_redirect(
    *, scan_run: "ScanRun", target: "ScanTarget",
    auth_endpoint: str, mutation_class: str, classification,
) -> None:
    severity = Severity.HIGH if classification.status == "confirmed" else Severity.MEDIUM
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug="2.14",
        title="OAuth redirect URI validation weakness",
        category="oauth_redirect_uri_issues",
        severity=severity,
        confidence=classification.confidence,
        status=FindingStatus.CANDIDATE,
        data={
            "auth_endpoint": auth_endpoint,
            "mutation_class": mutation_class,
            "location_origin": classification.location_origin,
            "requires_manual_review": True,
        },
    )
    log_finding_candidate(finding, stub_id="2.14")
