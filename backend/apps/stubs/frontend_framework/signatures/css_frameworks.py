"""CSS-framework signatures (Bootstrap, etc.)."""
from __future__ import annotations

from typing import Any


CSS_FRAMEWORK_SIGNATURES: list[dict[str, Any]] = [
    # Bootstrap
    {
        "id": "bootstrap_css_path",
        "technology": "Bootstrap",
        "category": "css_framework",
        "source": "script_src_path",
        "match_type": "regex",
        "value_pattern": r"bootstrap(?:-[\d.]+)?(?:\.min)?\.(?:js|css)",
        "version_regex": r"bootstrap[/-]([\d.]+)",
        "confidence": "medium",
    },
]
