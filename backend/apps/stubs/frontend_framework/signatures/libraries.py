"""Library-category signatures (HTMX, Alpine.js, Stimulus, Turbo, jQuery)."""
from __future__ import annotations

from typing import Any


LIBRARY_SIGNATURES: list[dict[str, Any]] = [
    # HTMX
    {
        "id": "htmx_attribute",
        "technology": "HTMX",
        "category": "library",
        "source": "html_body",
        "match_type": "regex",
        "value_pattern": r'\bhx-(get|post|target|swap|trigger)=',
        "version_regex": None,
        "confidence": "medium",
    },
    # Alpine.js
    {
        "id": "alpine_x_data",
        "technology": "Alpine.js",
        "category": "library",
        "source": "html_body",
        "match_type": "regex",
        "value_pattern": r'\bx-data=',
        "version_regex": None,
        "confidence": "medium",
    },
    # Stimulus
    {
        "id": "stimulus_controller",
        "technology": "Stimulus",
        "category": "library",
        "source": "html_body",
        "match_type": "regex",
        "value_pattern": r'\bdata-controller=',
        "version_regex": None,
        "confidence": "medium",
    },
    # Turbo
    {
        "id": "turbo_frame",
        "technology": "Turbo",
        "category": "library",
        "source": "html_body",
        "match_type": "contains",
        "value_pattern": "<turbo-frame",
        "version_regex": None,
        "confidence": "medium",
    },
    # jQuery
    {
        "id": "jquery_script_path",
        "technology": "jQuery",
        "category": "library",
        "source": "script_src_path",
        "match_type": "regex",
        "value_pattern": r"jquery(?:-[\d.]+)?(?:\.min)?\.js",
        "version_regex": r"jquery-([\d.]+)(?:\.min)?\.js",
        "confidence": "medium",
    },
]
