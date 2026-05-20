"""Pure-function classification for stub 1.10 probe responses.

Maps an HTTP probe response into a Verdict per spec §Response
classification + §Confidence rules. No I/O, no DB access.

Returns None when the probe should NOT yield a finding:
- 404/410 (hard not-found)
- body matches the homepage baseline (SPA fallthrough / generic 200)
- no body/header evidence on a non-high-signal path
- 401/403 on a non-high-signal path

MVP scope: framework signature, env leak, stack trace, and auth-
boundary verdicts. Redirect classification (spec §Redirect handling
row `redirect_live`) is deferred — `follow_redirects=False` at the
fetcher level guarantees we never chase off-origin Location, but
classifying 3xx-with-login-Location as `candidate/low` needs the
shared same-origin helper (#86) before lifting cleanly.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/10-debug-pages.md
"""
from __future__ import annotations

from typing import NamedTuple

from apps.findings.models import FindingStatus

from .._shared.types import Confidence
from .signals import (
    find_env_leak_markers,
    find_stack_trace_markers,
    match_framework_signature,
)
from .signatures import DebugPageKind


_NOT_FOUND_STATUSES = {404, 410}
_AUTH_BOUNDARY_STATUSES = {401, 403}


class Verdict(NamedTuple):
    kind: DebugPageKind
    # Spec §Persistence DebugPageExposure value
    exposure: str  # "public" | "blocked" | "login_required" | "redirected" | "unknown"
    confidence: Confidence
    finding_status: FindingStatus
    indicators: list[str]
    leaked_data_classes: list[str]


# Path-prefix → expected kind. The runner uses this to label a finding
# when only the path is signal (e.g. 401 on /actuator/env). When the
# body matches a framework signature, the signature's `kind` wins —
# the body is authoritative over the path. Ordering matters: longer
# prefixes come first so `/actuator/heapdump` resolves to
# `spring_actuator` before falling through to anything shorter.
_PATH_KIND_HINTS: tuple[tuple[str, DebugPageKind], ...] = (
    ("/laravel/telescope", "laravel_telescope"),
    ("/telescope", "laravel_telescope"),
    ("/horizon", "laravel_horizon"),
    ("/_ignition", "laravel_ignition"),
    ("/__debugbar", "laravel_debugbar"),  # 1.18 spec
    ("/_debug_toolbar", "django_debug_toolbar"),
    ("/_profiler", "symfony_profiler"),
    ("/profiler", "symfony_profiler"),
    ("/actuator", "spring_actuator"),
    ("/debug/pprof", "go_pprof"),
    ("/__debugger__", "werkzeug_debugger"),
    ("/werkzeug/console", "werkzeug_debugger"),
    ("/rails/info", "rails_info"),
    ("/server-status", "apache_server_status"),
    ("/server-info", "apache_server_info"),
    ("/trace.axd", "aspnet_tracing"),  # 1.18 spec
    ("/elmah.axd", "elmah"),  # 1.18 spec
    ("/debug/default", "yii_debug"),  # 1.18 spec
    ("/web-console", "jboss_wildfly_console"),  # 1.18 spec
    ("/phpinfo.php", "phpinfo"),
    ("/phpinfo", "phpinfo"),
    ("/info.php", "phpinfo"),
)


def _path_kind_hint(path: str) -> DebugPageKind | None:
    """Return the expected DebugPageKind for a path based on prefix
    match, or None when the path isn't a high-signal debug surface."""
    lowered = path.lower()
    for prefix, kind in _PATH_KIND_HINTS:
        if lowered.startswith(prefix):
            return kind
    return None


def classify_probe(
    path: str, probe: dict, baseline_body: str,
) -> Verdict | None:
    """Per-probe classification. Returns None when no finding should
    be emitted; otherwise a Verdict ready for persistence."""
    status = probe["status"]
    if status in _NOT_FOUND_STATUSES:
        return None

    body = probe.get("body") or ""
    if body and body == baseline_body:
        return None

    headers = probe.get("headers") or {}
    content_type = headers.get("content-type", "")

    # Scan body once, fan the results out to the three CONFIRMED
    # branches so each marker pass runs at most once per probe.
    env_markers = find_env_leak_markers(body)
    stack_markers = find_stack_trace_markers(body)
    leaked = env_markers + stack_markers

    # Body evidence trumps path: a framework signature anywhere is
    # authoritative regardless of the path the probe came from.
    match = match_framework_signature(body, content_type)
    if match is not None:
        return Verdict(
            kind=match.kind,
            exposure="public",
            confidence="high",
            finding_status=FindingStatus.CONFIRMED,
            indicators=[f"signature:{m}" for m in match.markers_matched],
            leaked_data_classes=leaked,
        )

    if env_markers:
        return Verdict(
            kind="environment_leak",
            exposure="public",
            confidence="high",
            finding_status=FindingStatus.CONFIRMED,
            indicators=[f"env_leak:{m}" for m in env_markers],
            leaked_data_classes=leaked,
        )

    if stack_markers:
        return Verdict(
            kind="stack_trace",
            exposure="public",
            confidence="high",
            finding_status=FindingStatus.CONFIRMED,
            indicators=[f"trace:{m}" for m in stack_markers],
            leaked_data_classes=stack_markers,
        )

    # No body evidence — path-based candidacy only.
    path_kind = _path_kind_hint(path)
    if path_kind is None:
        return None

    # Auth-gated on a high-signal debug path → candidate/medium. Spec
    # §Confidence rules: "debug-looking path is blocked but clearly
    # exists" — proof the resource exists, just not accessible to us.
    if status in _AUTH_BOUNDARY_STATUSES:
        return Verdict(
            kind=path_kind,
            exposure="blocked",
            confidence="medium",
            finding_status=FindingStatus.CANDIDATE,
            indicators=[f"status:{status}", f"path_hint:{path}"],
            leaked_data_classes=[],
        )

    # 200 on a high-signal path without body evidence is NOT a
    # finding — spec §Negative requires evidence beyond status+path.
    return None
