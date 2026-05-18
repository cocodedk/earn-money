"""Signature library for stub 1.3 frontend-framework.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/03-frontend-framework.md
"""
from __future__ import annotations

from typing import Any


CATEGORIES: set[str] = {
    "framework",
    "meta_framework",
    "library",
    "css_framework",
    "unknown",
}

MATCH_SOURCES: set[str] = {
    "html_body",
    "script_src_path",
    "asset_body",
}


SIGNATURES: list[dict[str, Any]] = [
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
    # Svelte / SvelteKit
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
    {
        "id": "sveltekit_data",
        "technology": "SvelteKit",
        "category": "meta_framework",
        "source": "html_body",
        "match_type": "contains",
        "value_pattern": "__SVELTEKIT_DATA__",
        "version_regex": None,
        "confidence": "high",
    },
    {
        "id": "sveltekit_immutable_path",
        "technology": "SvelteKit",
        "category": "meta_framework",
        "source": "script_src_path",
        "match_type": "contains",
        "value_pattern": "/_app/immutable/",
        "version_regex": None,
        "confidence": "high",
    },
    # Next.js
    {
        "id": "next_data",
        "technology": "Next.js",
        "category": "meta_framework",
        "source": "html_body",
        "match_type": "contains",
        "value_pattern": "__NEXT_DATA__",
        "version_regex": None,
        "confidence": "high",
    },
    {
        "id": "next_static_path",
        "technology": "Next.js",
        "category": "meta_framework",
        "source": "script_src_path",
        "match_type": "contains",
        "value_pattern": "/_next/static/",
        "version_regex": None,
        "confidence": "high",
    },
    # Nuxt
    {
        "id": "nuxt_global",
        "technology": "Nuxt",
        "category": "meta_framework",
        "source": "html_body",
        "match_type": "contains",
        "value_pattern": "__NUXT__",
        "version_regex": None,
        "confidence": "high",
    },
    {
        "id": "nuxt_static_path",
        "technology": "Nuxt",
        "category": "meta_framework",
        "source": "script_src_path",
        "match_type": "contains",
        "value_pattern": "/_nuxt/",
        "version_regex": None,
        "confidence": "high",
    },
    # Gatsby
    {
        "id": "gatsby_marker",
        "technology": "Gatsby",
        "category": "meta_framework",
        "source": "html_body",
        "match_type": "contains",
        "value_pattern": "___gatsby",
        "version_regex": None,
        "confidence": "high",
    },
    # Astro
    {
        "id": "astro_island",
        "technology": "Astro",
        "category": "meta_framework",
        "source": "html_body",
        "match_type": "contains",
        "value_pattern": "astro-island",
        "version_regex": None,
        "confidence": "high",
    },
    # Remix
    {
        "id": "remix_context",
        "technology": "Remix",
        "category": "meta_framework",
        "source": "html_body",
        "match_type": "contains",
        "value_pattern": "__remixContext",
        "version_regex": None,
        "confidence": "high",
    },
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
