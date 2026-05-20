"""Wrap untrusted scanned content for safe inclusion in LLM prompts.

Spec §7 + §9. Every byte the agent sees that originated outside the
operator's trust boundary (recon outputs, scanned HTML, fetched JS
bundles, exposed sourcemaps, ticket descriptions, API responses)
flows through `wrap_evidence(...)` first.

The wrapper:
- normalizes the text (strip C0 control chars, collapse zero-width
  unicode, optionally truncate),
- hashes the original bytes for an audit trail,
- runs the injection detector and stamps the result into the metadata,
- serializes the whole thing into a single XML-ish block the model is
  told (via the policy prompt) is data only.

The block format is deliberately uglier than freeform text so it's
harder for the model to confuse with conversational input.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from earn_money.agent.injection_detector import detect_injection

# Match C0 controls (except \t \n) + invisible Unicode classes:
# zero-width space, ZW joiner, ZW non-joiner, BOM, soft hyphen, RTL/LRT
# marks, ideographic space. These are common steganography vectors.
_INVISIBLE = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f"
    r"­​-‏‪-‮⁠-⁤⁪-⁯﻿]"
)


@dataclass(frozen=True)
class Evidence:
    """Normalized, hashed, scanned-content wrapper with metadata."""
    evidence_id: str
    source_type: str          # e.g. "http_response_body", "nuclei_signal"
    source_uri: str | None
    content_type: str | None
    content_hash: str         # sha256 of the ORIGINAL bytes
    scan_timestamp: str       # ISO 8601 UTC
    truncated: bool
    injection_suspected: bool
    injection_indicators: tuple[str, ...]
    normalized: str = field(repr=False)

    def to_block(self) -> str:
        """Serialize to the <UNTRUSTED_SCANNED_EVIDENCE> block format."""
        meta = (
            f'id="{self.evidence_id}" '
            f'source="{self.source_type}" '
            f'content_type="{self.content_type or "unknown"}" '
            f'hash="{self.content_hash[:16]}" '
            f'scanned_at="{self.scan_timestamp}" '
            f'truncated="{str(self.truncated).lower()}" '
            f'injection_suspected="{str(self.injection_suspected).lower()}"'
        )
        return (
            f"<UNTRUSTED_SCANNED_EVIDENCE {meta}>\n"
            f"{self.normalized}\n"
            "</UNTRUSTED_SCANNED_EVIDENCE>"
        )

    def to_metadata(self) -> dict[str, Any]:
        """Audit-trail subset for embedding in a runner's manifest."""
        return {
            "evidence_id": self.evidence_id,
            "source_type": self.source_type,
            "source_uri": self.source_uri,
            "content_type": self.content_type,
            "content_hash": self.content_hash,
            "scan_timestamp": self.scan_timestamp,
            "truncated": self.truncated,
            "injection_suspected": self.injection_suspected,
            "injection_indicators": list(self.injection_indicators),
        }


def wrap_evidence(
    content: str,
    *,
    evidence_id: str,
    source_type: str,
    source_uri: str | None = None,
    content_type: str | None = None,
    max_chars: int = 8_000,
    now: str | None = None,
) -> Evidence:
    """Build an `Evidence` from raw scanned content."""
    raw_bytes = content.encode("utf-8", errors="replace")
    content_hash = hashlib.sha256(raw_bytes).hexdigest()
    normalized, truncated = _normalize(content, max_chars=max_chars)
    scan_result = detect_injection(normalized)
    return Evidence(
        evidence_id=evidence_id,
        source_type=source_type,
        source_uri=source_uri,
        content_type=content_type,
        content_hash=content_hash,
        scan_timestamp=now or datetime.now(UTC).isoformat(),
        truncated=truncated,
        injection_suspected=scan_result.suspected,
        injection_indicators=scan_result.indicators,
        normalized=normalized,
    )


def _normalize(content: str, *, max_chars: int) -> tuple[str, bool]:
    """Strip invisible/control chars and truncate. Returns (text, truncated)."""
    stripped = _INVISIBLE.sub("", content)
    if len(stripped) <= max_chars:
        return stripped, False
    # Keep head + tail with a marker — pure head-truncation hides
    # malicious tail; pure tail hides head context. The marker line is
    # itself wrapped by the outer block so the model won't read it as
    # an instruction.
    head = stripped[: max_chars // 2]
    tail = stripped[-max_chars // 2 :]
    return f"{head}\n[…TRUNCATED…]\n{tail}", True
