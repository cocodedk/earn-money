"""Seeded candidate paths for stub 1.10.

MVP scope per spec §Candidate paths "standard" profile: the curated
list of debug / profiler / diagnostic / actuator / route-inspection
paths. `minimal` and `extended` profiles are deferred until the
runner needs them.

`path_wordlist_profile` config is also deferred — the runner emits
this single set against every target. Discovered-path merging
(robots/sitemap/JS-route output) is wired through `extra_paths` on
the fetcher per the established Phase-1 pattern.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/10-debug-pages.md
"""
from __future__ import annotations


# `standard` profile — the spec's recommended baseline. Slash variants
# (`/debug` and `/debug/`) are kept because frameworks differ on which
# form is canonical (Spring actuator prefers `/actuator`, Symfony
# `/_profiler/`, Werkzeug `/__debugger__` without trailing slash).
# Slash-dedup at finding level is a follow-up shared with stub 1.9.
SEEDED_PATHS: tuple[str, ...] = (
    # Generic debug surfaces
    "/debug",
    "/debug/",
    "/debug/vars",
    "/debug/default/view",
    "/_debug_toolbar/",
    "/_debug_toolbar",
    "/__debugger__",
    "/console",
    "/console/",
    "/werkzeug/console",
    # Profilers
    "/_profiler/",
    "/_profiler",
    "/_profiler/phpinfo",
    "/_profiler/empty/search/results",
    "/profiler",
    "/profiler/",
    "/debug/pprof",
    "/debug/pprof/",
    "/debug/pprof/cmdline",
    "/debug/pprof/goroutine",
    # PHPInfo
    "/phpinfo.php",
    "/phpinfo",
    "/info.php",
    # Apache mod_status / mod_info
    "/server-status",
    "/server-status/",
    "/server-info",
    "/server-info/",
    # Spring Boot actuator
    "/actuator",
    "/actuator/",
    "/actuator/health",
    "/actuator/info",
    "/actuator/env",
    "/actuator/configprops",
    "/actuator/beans",
    "/actuator/mappings",
    "/actuator/threaddump",
    "/actuator/heapdump",
    "/actuator/prometheus",
    # Rails / routes
    "/routes",
    "/routes/",
    "/rails/info/routes",
    "/rails/info/properties",
    # Laravel diagnostic surfaces
    "/laravel/telescope",
    "/telescope",
    "/telescope/",
    "/horizon",
    "/_ignition/health-check",
    "/_ignition/execute-solution",  # GET probe only — spec §forbidden
    # Dev-server debug
    "/_next/static/development/_devMiddlewareManifest.json",
    "/vite/client",
    "/__vite_ping",
)


# Headers the fetcher captures from responses. Spec §Medium indicators
# names X-Debug-Token, X-Debug-Token-Link, X-Runtime as debug-specific.
# Location is captured for redirect classification per spec §Redirect
# handling. The cookie / authorization / set-cookie families are
# DELIBERATELY excluded — spec §Safety "Must not persist cookies,
# authorization headers, tokens".
CAPTURED_HEADERS: tuple[str, ...] = (
    "content-type",
    "location",
    "x-debug-token",
    "x-debug-token-link",
    "x-runtime",
    "x-powered-by",
)
