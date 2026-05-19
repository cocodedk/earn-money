"""Stack-trace matcher for stub 1.16 (slice 1).

`detect_stack_traces(body, content_type)` walks the SIGNATURES
table (signatures.py) and returns one StackTraceMatch per family
that matches. JSON responses are also scanned over a flattened
view of all string values so a stack-bearing `stack` field gets
the same regex treatment as plain-text body.

Pure function — no I/O.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/16-stack-traces.md
"""
from __future__ import annotations

import json
from typing import NamedTuple

from .signatures import SIGNATURES, Family, Language, Signature


class StackTraceMatch(NamedTuple):
    family: Family
    language: Language
    framework: str | None
    exception_type: str | None
    top_frame: str | None
    stack_frame_count: int


def detect_stack_traces(body: str, content_type: str) -> list[StackTraceMatch]:
    if not body:
        return []
    haystacks = _haystacks(body, content_type)
    matches: list[StackTraceMatch] = []
    for sig in SIGNATURES:
        for haystack in haystacks:
            if sig.required_re.search(haystack):
                matches.append(_build_match(sig, haystack))
                # One match per family even when both raw body and
                # flattened JSON haystacks would match — JSON-walked
                # views are a fallback, not a duplicate channel.
                break
    return matches


def _build_match(sig: Signature, body: str) -> StackTraceMatch:
    # frames empty when the family anchor matches but no frames were
    # emitted (e.g. Whitelabel Error Page without Java stack lines).
    frames: list[tuple[str, ...]] = sig.frame_re.findall(body)
    top_frame = (
        ":".join(part for part in frames[0] if part) if frames else None
    )
    exception = None
    if sig.exception_re is not None:
        em = sig.exception_re.search(body)
        if em is not None:
            exception = em.group(1).strip()
    return StackTraceMatch(
        family=sig.family, language=sig.language, framework=sig.framework,
        exception_type=exception, top_frame=top_frame,
        stack_frame_count=len(frames),
    )


def _haystacks(body: str, content_type: str) -> list[str]:
    """JSON responses get an extra pass over flattened string values
    so a stack-bearing `stack` field matches the same patterns as a
    plain-text body."""
    if "json" in content_type.lower():
        flattened = _flatten_json_strings(body)
        if flattened:
            return [body, flattened]
    return [body]


def _flatten_json_strings(body: str) -> str:
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return ""
    parts: list[str] = []
    _walk_strings(data, parts)
    return "\n".join(parts)


def _walk_strings(node, parts: list[str]) -> None:
    if isinstance(node, str):
        parts.append(node)
    elif isinstance(node, dict):
        for v in node.values():
            _walk_strings(v, parts)
    elif isinstance(node, list):
        for v in node:
            _walk_strings(v, parts)
