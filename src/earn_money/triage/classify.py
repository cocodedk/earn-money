"""Signal classification dispatch: derives (vuln_class, title, severity_hint,
confidence) from a Signal's tool + signal_type + payload.

Keeping this module separate from the engine keeps both files under the
200-line cap and makes the dispatch table easy to extend.
"""

from __future__ import annotations

import json
from typing import Any

from earn_money.recon.signals import Signal

# Return type alias: (vuln_class, title, severity_hint, confidence)
Classification = tuple[str, str, str, int]

_SEVERITY_CONFIDENCE: dict[str, int] = {
    "critical": 80,
    "high": 70,
    "medium": 50,
    "low": 35,
    "info": 30,
}


def classify(sig: Signal) -> Classification:
    """Derive (vuln_class, title, severity_hint, confidence) from a signal."""
    if sig.tool == "nuclei" and sig.signal_type == "template_match":
        return _classify_nuclei_match(sig)
    if sig.tool == "nuclei" and sig.signal_type == "prereq_missing":
        return (
            "recon-prereq-missing",
            "nuclei skipped: no recent httpx run",
            "info",
            100,
        )
    if sig.tool == "httpx" and sig.signal_type == "fingerprint_drift":
        return (
            "recon-fingerprint-drift",
            f"httpx fingerprint changed on {sig.asset}",
            "info",
            40,
        )
    return (
        "recon-other",
        f"{sig.tool}/{sig.signal_type} on {sig.asset}",
        "unknown",
        0,
    )


def _classify_nuclei_match(sig: Signal) -> Classification:
    try:
        payload: dict[str, Any] = json.loads(sig.payload)
    except json.JSONDecodeError:
        payload = {}
    template_id = str(payload.get("template_id", "unknown")).lower()
    severity = str(payload.get("severity", "unknown")).lower()
    name = str(payload.get("name") or template_id)
    confidence = _SEVERITY_CONFIDENCE.get(severity, 30)
    title = f"{name} on {sig.asset}"
    return (template_id, title, severity, confidence)
