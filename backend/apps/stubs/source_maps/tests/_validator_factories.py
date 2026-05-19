"""Shared factory helpers for source_maps validator tests."""
from __future__ import annotations


def minimal_v3() -> dict:
    return {
        "version": 3,
        "file": "app.min.js",
        "sources": ["webpack://app/src/main.ts"],
        "sourcesContent": ["console.log('main');"],
        "names": [],
        "mappings": "AAAA",
    }
