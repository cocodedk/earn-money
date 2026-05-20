"""Finding persistence for stub 1.15 — see 15-public-javascript-bundles.md.

Each fetched candidate yields one Finding row whose `data` carries
the spec's PublicJavascriptBundleSignature shape (lines 222-262).
Cross-run idempotence (signature upsert by (scan_target_id,
bundle_url)) and the stale-status flip are deferred — current pass
always creates new rows, same MVP shape as stub 1.14.

Severity stays at `info` per spec §Persistence default ("Use `low`
only when deterministic evidence shows sensitive public metadata") —
the severity-lift path lives in a future enhancement.
"""
from __future__ import annotations

from apps.findings.models import Finding, FindingStatus, Severity
from apps.scans.models import ScanRun
from apps.targets.models import ScanTarget

from .body_text_extractors import (
    extract_api_path_hints,
    extract_public_env_names,
    extract_suspicious_indicators,
)
from .classifier import Verdict, classify
from .content_extractors import (
    extract_build_hints,
    extract_extension_from_filename,
    extract_filename,
    extract_hash_in_filename,
    extract_minified_marker,
    extract_source_map_url,
)
from .fetcher import BundleFetchOutcome
from .framework_hints import extract_framework_hints
from .parser import BundleCandidate
from .secret_redactors import extract_token_indicators


_STUB_SLUG = "1.15"
_CATEGORY = "public_javascript_bundles"


def emit_finding(
    scan_run: ScanRun, target: ScanTarget,
    candidate: BundleCandidate, outcome: BundleFetchOutcome,
    *, html_url: str, evidence_ids: list[str],
) -> Finding:
    verdict = classify(
        fetch_kind=outcome.kind,
        content_type_is_js=outcome.content_type_matched_allowlist,
    )
    body = outcome.body if outcome.kind == "ok" else ""
    data = _build_signature_data(
        candidate, outcome, body, html_url, evidence_ids,
    )
    return _persist(scan_run, target, candidate.url, verdict, data)


def emit_unfetched_finding(
    scan_run: ScanRun, target: ScanTarget,
    candidate: BundleCandidate, *, html_url: str,
    evidence_ids: list[str],
) -> Finding:
    """Cross-origin candidate the runner deliberately skipped
    (include_cdn_metadata=false). Recorded as low-confidence
    candidate so the operator can audit external script
    references without the runner ever fetching them."""
    verdict = classify(fetch_kind=None, content_type_is_js=False)
    data = {
        "bundle_url": candidate.url,
        "discovered_from_url": html_url,
        "same_origin": False,
        "script_type": candidate.script_type,
        "discovery_method": candidate.discovery_method,
        "evidence_ids": evidence_ids,
        "skipped_reason": "cross_origin_no_include_cdn_metadata",
    }
    return _persist(scan_run, target, candidate.url, verdict, data)


def _persist(
    scan_run: ScanRun, target: ScanTarget, bundle_url: str,
    verdict: Verdict, data: dict,
) -> Finding:
    finding = Finding(
        scan_run=scan_run, target=target, stub_slug=_STUB_SLUG,
        title=f"Public JS bundle: {bundle_url[:200]}",
        category=_CATEGORY, severity=Severity.INFO,
        confidence=verdict.confidence, status=verdict.status,
        data=data,
    )
    finding.save()
    return finding


def _build_signature_data(
    candidate: BundleCandidate, outcome: BundleFetchOutcome,
    body: str, html_url: str, evidence_ids: list[str],
) -> dict:
    filename = extract_filename(candidate.url) or ""
    framework_hints = [
        {"name": h.name, "matched_pattern": h.matched_pattern,
         "confidence": h.confidence}
        for h in extract_framework_hints(body)
    ]
    return {
        "discovered_from_url": html_url,
        "bundle_url": candidate.url,
        "final_url": outcome.final_url,
        "same_origin": candidate.same_origin,
        "status_code": outcome.status,
        "content_type": outcome.content_type,
        "content_length": outcome.content_length,
        "bytes_read": outcome.bytes_read,
        "truncated": outcome.truncated,
        "sha256": outcome.sha256,
        "etag": outcome.etag,
        "last_modified": outcome.last_modified,
        "cache_control": outcome.cache_control,
        "script_type": candidate.script_type,
        "discovery_method": candidate.discovery_method,
        "filename": filename,
        "extension": extract_extension_from_filename(filename),
        "hash_in_filename": extract_hash_in_filename(filename),
        "minified": extract_minified_marker(body),
        "source_map_url": extract_source_map_url(body),
        "framework_hints": framework_hints,
        "build_hints": extract_build_hints(filename),
        "public_env_names": extract_public_env_names(body),
        "api_path_hints": extract_api_path_hints(body),
        "external_host_hints": extract_suspicious_indicators(body),
        "token_like_indicator_count": len(extract_token_indicators(body)),
        "evidence_ids": evidence_ids,
    }
