"""Candidate admin paths for stub 1.8.

MVP scope per spec §Default candidate paths: 12 high-signal entries
covering generic admin variants + WordPress + framework consoles.
Spec lists ~40 paths; the larger set is deferred to a follow-up since
the soft-404 filter already shoulders most of the precision work.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/08-exposed-admin-panels.md
"""
from __future__ import annotations


CANDIDATE_PATHS: tuple[str, ...] = (
    "/admin",
    "/admin/",
    "/administrator",
    "/admin/login",
    "/backend",
    "/console",
    "/cpanel",
    "/dashboard",
    "/manage",
    "/manager",
    "/panel",
    "/wp-admin/",
    "/wp-login.php",
)
