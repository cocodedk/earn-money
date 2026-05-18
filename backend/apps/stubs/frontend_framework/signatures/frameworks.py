"""Framework-category signatures (Angular, AngularJS, React, Vue, Svelte)."""
from __future__ import annotations

from typing import Any


FRAMEWORK_SIGNATURES: list[dict[str, Any]] = [
    # Angular
    {
        "id": "angular_ng_version",
        "technology": "Angular",
        "category": "framework",
        "source": "html_body",
        "match_type": "regex",
        "value_pattern": r'ng-version="[\d.]+"',
        "version_regex": r'ng-version="([\d.]+)"',
        "confidence": "high",
    },
    {
        "id": "angular_ngcontent_marker",
        "technology": "Angular",
        "category": "framework",
        "source": "html_body",
        "match_type": "contains_all",
        "value_pattern": ["_ngcontent-", "-ng-"],
        "version_regex": None,
        "confidence": "medium",
    },
    {
        "id": "angular_bundle_paths",
        "technology": "Angular",
        "category": "framework",
        "source": "script_src_path",
        "match_type": "contains_all",
        "value_pattern": ["runtime", "polyfills", "main"],
        "version_regex": None,
        "confidence": "medium",
    },
    # AngularJS
    {
        "id": "angularjs_script_path",
        "technology": "AngularJS",
        "category": "framework",
        "source": "script_src_path",
        "match_type": "contains",
        "value_pattern": "angular.js",
        "version_regex": None,
        "confidence": "medium",
    },
    # React
    {
        "id": "react_dom_in_asset",
        "technology": "React",
        "category": "framework",
        "source": "asset_body",
        "match_type": "contains",
        "value_pattern": "react-dom",
        "version_regex": None,
        "confidence": "medium",
    },
    {
        "id": "react_data_reactroot",
        "technology": "React",
        "category": "framework",
        "source": "html_body",
        "match_type": "contains",
        "value_pattern": "data-reactroot",
        "version_regex": None,
        "confidence": "medium",
    },
    {
        "id": "react_devtools_hook",
        "technology": "React",
        "category": "framework",
        "source": "asset_body",
        "match_type": "contains",
        "value_pattern": "__REACT_DEVTOOLS_GLOBAL_HOOK__",
        "version_regex": None,
        "confidence": "low",
    },
    # Vue
    {
        "id": "vue_runtime_in_asset",
        "technology": "Vue",
        "category": "framework",
        "source": "asset_body",
        "match_type": "contains",
        "value_pattern": "vue.runtime",
        "version_regex": None,
        "confidence": "medium",
    },
    {
        "id": "vue_global_marker",
        "technology": "Vue",
        "category": "framework",
        "source": "asset_body",
        "match_type": "contains",
        "value_pattern": "__VUE__",
        "version_regex": None,
        "confidence": "medium",
    },
    # Svelte
    {
        "id": "svelte_data_h",
        "technology": "Svelte",
        "category": "framework",
        "source": "html_body",
        "match_type": "contains",
        "value_pattern": "data-svelte-h",
        "version_regex": None,
        "confidence": "high",
    },
]
