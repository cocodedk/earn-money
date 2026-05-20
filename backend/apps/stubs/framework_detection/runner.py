"""Framework-detection runner — registered against stub_slug "1.1".

The Celery task dispatcher (apps.scans.tasks._process_target_run) calls
`run(scan_run, target_run)` between the platform-emitted
scan_target_run.started / scan_target_run.done events.

Workflow per target:
1. Fetch evidence (HTTP GET on the target root + parse).
2. For each signature in the library, check if it matches the evidence.
3. Group matched signatures by `technology`.
4. Write one `Evidence` row per matched signature, one `Finding` row
   per detected technology — bulk-inserted inside one transaction so a
   crash never leaves orphan Evidence rows for a missing Finding.
5. The `Finding` carries the highest confidence of all signatures that
   contributed to it.

The runner's job ends here — platform code emits scan_run.done after
all targets are processed.
"""
from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.evidence.models import Evidence
from apps.findings.confidence import max_confidence
from apps.findings.models import Finding, FindingStatus, Severity
from apps.findings.bulk import bulk_create_findings
from apps.scans.models import ScanRun, ScanTargetRun

from .._shared.hashing import prefixed_body_hash
from ..runners import register
from .fetcher import fetch_evidence
from .matcher import matches
from .signatures import SIGNATURES


@register("1.1")
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:
    target = target_run.target
    bundle = fetch_evidence(target.base_url)

    matched: list[dict[str, Any]] = [
        sig for sig in SIGNATURES if matches(sig, bundle)
    ]
    if not matched:
        return

    by_tech: dict[str, list[dict[str, Any]]] = {}
    for sig in matched:
        by_tech.setdefault(sig["technology"], []).append(sig)

    body_hash = prefixed_body_hash(bundle.get("html_body", ""))

    evidences_to_create: list[Evidence] = []
    findings_to_create: list[Finding] = []

    for technology, sigs in by_tech.items():
        tech_evidences = [
            Evidence(
                scan_run=scan_run,
                target=target,
                source=sig["source"],
                url=bundle["url"],
                method="GET",
                field=sig["field"],
                matched_value=_matched_value(sig),
                raw_excerpt=_excerpt_for(sig, bundle),
                content_hash=body_hash,
                data={
                    "signature_id": sig["id"],
                    "category": sig["category"],
                    "match_type": sig["match_type"],
                    "technology": technology,
                },
            )
            for sig in sigs
        ]
        evidences_to_create.extend(tech_evidences)
        findings_to_create.append(
            Finding(
                scan_run=scan_run,
                target=target,
                stub_slug=scan_run.stub_slug,
                title=f"{technology} detected on {target.host}",
                category=sigs[0]["category"],
                severity=Severity.INFO,
                confidence=max_confidence(sigs),
                status=FindingStatus.CANDIDATE,
                data={
                    "technology": technology,
                    "evidence_ids": [str(e.id) for e in tech_evidences],
                    "signature_ids": [sig["id"] for sig in sigs],
                    "method": "deterministic_signature",
                },
            )
        )

    with transaction.atomic():
        Evidence.objects.bulk_create(evidences_to_create)
        bulk_create_findings(findings_to_create)


def _matched_value(signature: dict[str, Any]) -> str:
    if signature["match_type"] == "contains_all":
        return ",".join(signature["patterns"])
    return signature["pattern"]


def _excerpt_for(signature: dict[str, Any], bundle: dict[str, Any]) -> str:
    source = signature["source"]
    if source == "header":
        value = bundle.get("headers", {}).get(signature["field"], "")
        return f"{signature['field']}: {value}"[:200]
    if source == "cookie":
        names = [c["name"] for c in bundle.get("cookies", [])]
        return f"cookies: {names}"[:200]
    if source == "html" and signature["field"] == "script_names":
        return f"scripts: {bundle.get('script_names', [])}"[:200]
    body = bundle.get("html_body", "")
    idx = body.find(signature["pattern"])
    if idx < 0:
        return ""  # pragma: no cover  # matched() returned True so the pattern is in body; defense
    return body[max(0, idx - 40):idx + 160]
