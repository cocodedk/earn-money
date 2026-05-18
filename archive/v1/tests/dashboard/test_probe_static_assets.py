"""Static-asset safety + structure tests.

Three cheap regex assertions over source files:
- `probe-detail.js` has no DOM-write sinks (LLM-controlled strings must
  go through `textContent` only)
- `index.html` links `probe-detail.css` so the panel ships styled
- `index.html` loads the five probe JS files in dependency order

Promoted from the manual grep that lived in the spec; pytest-level so it
cannot be skipped.
"""
from __future__ import annotations

import re
from pathlib import Path

_BASE = Path(__file__).resolve().parents[2] / "src" / "earn_money" / "dashboard" / "templates"
_STATIC = _BASE / "static"
_INDEX = _BASE / "index.html"

# Author note: the regex matches raw bytes, including comments. Don't
# mention any of these names in probe-detail.js comments — the test
# would fail. Phrase as "use textContent" or "no DOM-write methods".
_FORBIDDEN = re.compile(
    r"\binnerHTML\b|\binsertAdjacentHTML\b|\bouterHTML\b"
    r"|\bdocument\.write\b|\bcreateContextualFragment\b"
)

_EXPECTED_SCRIPT_ORDER = [
    "/static/probe-status.js",
    "/static/probe-state.js",
    "/static/probe-render.js",
    "/static/probe-detail.js",
    "/static/probe.js",
    "/static/probe-pill.js",
]


def test_probe_detail_js_uses_no_html_sinks() -> None:
    src = (_STATIC / "probe-detail.js").read_text(encoding="utf-8")
    matches = [
        (i + 1, line) for i, line in enumerate(src.splitlines())
        if _FORBIDDEN.search(line)
    ]
    assert not matches, (
        "probe-detail.js must not use HTML-write sinks "
        "(innerHTML, insertAdjacentHTML, outerHTML, document.write, "
        f"createContextualFragment) — found {len(matches)} occurrence(s): {matches}"
    )


def test_index_html_loads_probe_detail_css() -> None:
    html = _INDEX.read_text(encoding="utf-8")
    assert '"/static/probe-detail.css"' in html, (
        "index.html must <link> to /static/probe-detail.css"
    )


def test_index_html_loads_probe_scripts_in_dependency_order() -> None:
    html = _INDEX.read_text(encoding="utf-8")
    found = re.findall(r'<script[^>]+src="(/static/probe[^"]*\.js)"', html)
    assert found == _EXPECTED_SCRIPT_ORDER, (
        f"index.html script order must be {_EXPECTED_SCRIPT_ORDER}, got {found}"
    )
