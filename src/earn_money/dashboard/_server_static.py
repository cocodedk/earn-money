"""Static-asset route table for the dashboard server.

Extracted from server.py to keep that module under the project's
200-line cap. The handler closes over the bytes-resolved dict that
`build_static_assets` returns; per-request lookups never hit disk.
"""
from __future__ import annotations

from pathlib import Path

_TEMPLATES = Path(__file__).parent / "templates"
_STATIC = _TEMPLATES / "static"

_CSS = "text/css; charset=utf-8"
_JS = "application/javascript; charset=utf-8"

# URL → (filesystem path, Content-Type).
STATIC_ROUTES: dict[str, tuple[Path, str]] = {
    "/static/tokens.css":            (_STATIC / "tokens.css",            _CSS),
    "/static/dashboard.css":         (_STATIC / "dashboard.css",         _CSS),
    "/static/dashboard-base.css":    (_STATIC / "dashboard-base.css",    _CSS),
    "/static/dashboard-header.css":  (_STATIC / "dashboard-header.css",  _CSS),
    "/static/dashboard-programs.css":(_STATIC / "dashboard-programs.css",_CSS),
    "/static/dashboard-footer.css":  (_STATIC / "dashboard-footer.css",  _CSS),
    "/static/panels.css":            (_STATIC / "panels.css",            _CSS),
    "/static/probe.css":             (_STATIC / "probe.css",             _CSS),
    "/static/render.js":        (_STATIC / "render.js",        _JS),
    "/static/render_panels.js": (_STATIC / "render_panels.js", _JS),
    "/static/dashboard.js":     (_STATIC / "dashboard.js",     _JS),
    "/static/tabs.js":          (_STATIC / "tabs.js",          _JS),
    "/static/probe.js":         (_STATIC / "probe.js",         _JS),
    "/static/probe-render.js":  (_STATIC / "probe-render.js",  _JS),
    "/static/probe-status.js":  (_STATIC / "probe-status.js",  _JS),
    "/static/probe-state.js":   (_STATIC / "probe-state.js",   _JS),
    "/static/probe-detail.css": (_STATIC / "probe-detail.css", _CSS),
    "/static/probe-detail.js":  (_STATIC / "probe-detail.js",  _JS),
    "/static/probe-pill.js":    (_STATIC / "probe-pill.js",    _JS),
}


def load_index_html() -> bytes:
    return (_TEMPLATES / "index.html").read_bytes()


def load_static_assets() -> dict[str, tuple[bytes, str]]:
    """Read every static asset at startup. A missing file is a fail-fast
    install bug: `FileNotFoundError` propagates and the server refuses
    to start."""
    return {
        url: (path.read_bytes(), ctype)
        for url, (path, ctype) in STATIC_ROUTES.items()
    }
