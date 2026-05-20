"""Meta-framework signatures (SvelteKit, Next.js, Nuxt, Gatsby, Astro, Remix)."""
from __future__ import annotations

from typing import Any


META_FRAMEWORK_SIGNATURES: list[dict[str, Any]] = [
    # SvelteKit
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
]
