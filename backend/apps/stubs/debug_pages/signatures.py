"""Framework signature library for stub 1.10.

Each `Signature` declares the body markers that uniquely identify a
debug page from a specific framework. The match rule is `body must
contain ALL `body_markers` (case-insensitive)`. The AND requirement
keeps the bar high — a single common word like "debug" or "PHP" by
itself is insufficient (spec §Negative: "must not confirm /status,
/health, or /info based on path and 200 status alone"; spec §
"must not create a high-confidence finding from a generic 404 page
that echoes the requested path").

`content_type_includes` narrows matching to specific content types
(e.g. Spring actuator only matches on `application/json`). Empty
tuple means content-type-agnostic.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/10-debug-pages.md
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# Spec §Persistence DebugPageKind closed string-union. Promoting to a
# Literal alias means typos like "phpinfo " or "spring-actuator" fail
# the type-check at signature-table construction time rather than as
# silent runtime mismatches downstream.
DebugPageKind = Literal[
    "phpinfo",
    "django_debug_toolbar",
    "symfony_profiler",
    "spring_actuator",
    "go_pprof",
    "werkzeug_debugger",
    "laravel_telescope",
    "laravel_horizon",
    "laravel_ignition",
    "rails_info",
    "apache_server_status",
    "apache_server_info",
    "stack_trace",
    "environment_leak",
    "route_listing",
    "generic_debug",
    "unknown",
]


@dataclass(frozen=True)
class Signature:
    kind: DebugPageKind
    # ALL markers must appear (case-insensitive) for a match. Two
    # markers ANDed beats one marker for false-positive resistance:
    # `phpinfo()` alone could be in a blog post, but with `PHP Version`
    # alongside it's the page.
    body_markers: tuple[str, ...]
    # Restrict matching to specific Content-Type values; empty tuple
    # = any content type. Used for spring_actuator (JSON only) so an
    # HTML page mentioning `_links` doesn't trigger a Spring finding.
    content_type_includes: tuple[str, ...] = field(default_factory=tuple)


# Each signature is one framework. Markers are pre-lowered so the
# matcher only has to lowercase the body once. Ordering doesn't matter
# for correctness — the matcher returns the first match. Putting more
# specific frameworks before generic ones avoids accidental
# generic-shadowing if a stricter signature becomes a subset of a
# looser one in the future.
FRAMEWORK_SIGNATURES: tuple[Signature, ...] = (
    Signature(
        kind="phpinfo",
        body_markers=("phpinfo()", "php version"),
    ),
    Signature(
        kind="django_debug_toolbar",
        body_markers=("djdebug", "sqlpanel"),
    ),
    Signature(
        kind="symfony_profiler",
        body_markers=("sf-toolbar", "symfony profiler"),
    ),
    Signature(
        kind="spring_actuator",
        body_markers=('"_links"', '"self"', '"health"'),
        content_type_includes=("application/json",),
    ),
    Signature(
        kind="go_pprof",
        body_markers=("types of profiles available", "goroutine"),
    ),
    Signature(
        kind="werkzeug_debugger",
        body_markers=("werkzeug debugger", "console locked"),
    ),
    Signature(
        kind="laravel_telescope",
        body_markers=("laravel telescope",),
    ),
    Signature(
        kind="laravel_horizon",
        body_markers=("laravel horizon",),
    ),
    Signature(
        # Whoops + _ignition together — Whoops alone is a generic
        # PHP error page, _ignition alone is the URL prefix; the
        # combination identifies the Ignition handler page.
        kind="laravel_ignition",
        body_markers=("whoops", "_ignition"),
    ),
    Signature(
        kind="rails_info",
        body_markers=("rails::infocontroller",),
    ),
    Signature(
        # "Apache Server Status" is the mod_status page title; the phrase
        # is unique enough on its own. Some deployments strip the
        # "Server Version: Apache/x.y" line behind reverse proxies, so
        # gating on it would reject real findings.
        kind="apache_server_status",
        body_markers=("apache server status",),
    ),
)
