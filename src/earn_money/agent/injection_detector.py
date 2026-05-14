"""Detect prompt-injection patterns inside scanned evidence.

Spec §8: deterministic-only matcher. Returns a list of indicators that
fired plus a boolean flag. The detector NEVER blocks scanning — it
annotates evidence so the LLM is warned + `requires_human_review`
flips on for downstream analysis.

The detector is intentionally simple: a curated regex catalogue,
no LLM, no embeddings. Cheap, auditable, and impossible to subvert
via the same content it inspects.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass

# Each pattern: (indicator_name, compiled regex). Indicator names are
# what flows into `injection_indicators` so a human reviewer sees
# *which* class fired without re-running the detector.
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ignore_previous", re.compile(
        r"ignore (?:previous|all (?:of the )?above|prior|the system)",
        re.IGNORECASE)),
    ("disregard_previous", re.compile(
        r"disregard (?:previous|all (?:of the )?above|prior)",
        re.IGNORECASE)),
    ("forget_previous", re.compile(
        r"forget (?:all (?:previous |of the above)?|previous|everything)",
        re.IGNORECASE)),
    ("role_change", re.compile(
        r"you are (?:now|actually) (?:a|an|the)\b", re.IGNORECASE)),
    ("act_as", re.compile(r"\bact as (?:a|an|the)\b", re.IGNORECASE)),
    ("system_prompt", re.compile(
        r"\b(?:system|developer) (?:prompt|message|role)\b", re.IGNORECASE)),
    ("reveal_prompt", re.compile(
        r"(?:reveal|print|leak|show me) (?:your |the )?(?:system )?"
        r"(?:prompt|instructions)",
        re.IGNORECASE)),
    ("tool_call_request", re.compile(
        r"(?:call|invoke|execute) (?:the |this )?tool\b", re.IGNORECASE)),
    ("call_url", re.compile(
        r"(?:call|fetch|GET|POST|visit) (?:this |the )?URL\b",
        re.IGNORECASE)),
    ("exfiltrate_to", re.compile(
        r"(?:exfiltrate|send|post|leak)(?: data)? to\s+https?://",
        re.IGNORECASE)),
    ("mark_safe", re.compile(
        r"(?:mark|classify|report) this (?:as |finding as )?safe",
        re.IGNORECASE)),
    ("do_not_report", re.compile(
        r"do not (?:report|disclose|surface) this", re.IGNORECASE)),
    ("delete_findings", re.compile(
        r"(?:delete|remove|purge) (?:these |this |the )?findings?",
        re.IGNORECASE)),
    ("suppress_finding", re.compile(
        r"suppress (?:this |the )?finding", re.IGNORECASE)),
    ("override_severity", re.compile(
        r"(?:override|change|reduce|lower) (?:the )?severity",
        re.IGNORECASE)),
    ("jailbreak", re.compile(r"\bjailbreak\b", re.IGNORECASE)),
    ("dan_persona", re.compile(r"\bDAN\b.*\b(?:mode|prompt)\b")),
    ("html_comment_injection", re.compile(r"<!--[^>]*(?:ignore|system|prompt)")),
    ("style_injection", re.compile(
        r"<style[^>]*>[^<]*(?:ignore|system|prompt)", re.IGNORECASE)),
    ("script_injection", re.compile(
        r"<script[^>]*>[^<]*(?:ignore|system|prompt)", re.IGNORECASE)),
)

# Heuristic: base64-encoded blobs ≥120 chars MAY contain hidden instructions.
# Decode and re-scan with the regex set; flag if any hit fires.
_BASE64_BLOB = re.compile(r"\b([A-Za-z0-9+/]{120,}={0,2})\b")


@dataclass(frozen=True)
class InjectionScan:
    suspected: bool
    indicators: tuple[str, ...]


def detect_injection(content: str) -> InjectionScan:
    """Scan `content` for prompt-injection patterns. Pure function."""
    matched: set[str] = set()
    for name, pattern in _PATTERNS:
        if pattern.search(content):
            matched.add(name)
    matched |= _scan_base64_blobs(content)
    return InjectionScan(
        suspected=bool(matched),
        indicators=tuple(sorted(matched)),
    )


def _scan_base64_blobs(content: str) -> set[str]:
    """Decode long base64-looking runs and re-scan. Returns the set of
    secondary indicator names, prefixed with `base64_`."""
    hits: set[str] = set()
    for match in _BASE64_BLOB.finditer(content):
        blob = match.group(1)
        try:
            decoded = base64.b64decode(blob, validate=True).decode(
                "utf-8", errors="ignore",
            )
        except (ValueError, OSError):
            continue
        if not decoded.strip():
            continue
        # Lightweight inner scan — only the most dangerous classes.
        inner_targets = (
            "ignore_previous", "disregard_previous",
            "system_prompt", "reveal_prompt",
            "call_url", "exfiltrate_to",
        )
        for name, pattern in _PATTERNS:
            if name in inner_targets and pattern.search(decoded):
                hits.add(f"base64_{name}")
    return hits
