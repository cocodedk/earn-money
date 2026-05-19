"""Candidate backup-file paths for stub 1.7.

MVP scope: a small fixed list of high-signal root-level backup,
config, dump, and editor-archive paths. Per-seed candidate generation
(extending observed paths with .bak/.old/.orig/etc.) is deferred to a
follow-up bullet — that requires seed-URL feed from other stubs.

Each entry pairs a path with the source_kind that classifies what
kind of leak it would represent if reachable.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/07-backup-files.md
"""
from __future__ import annotations


CANDIDATES: tuple[tuple[str, str], ...] = (
    ("/backup.zip", "archive"),
    ("/backup.tar.gz", "archive"),
    ("/site.zip", "archive"),
    ("/www.zip", "archive"),
    ("/source.zip", "archive"),
    ("/backup.sql", "db_dump"),
    ("/database.sql", "db_dump"),
    ("/dump.sql", "db_dump"),
    ("/.env", "secret_file"),
    ("/.env.bak", "secret_file"),
    ("/web.config", "config_file"),
    ("/wp-config.php.bak", "config_file"),
    ("/config.php.bak", "config_file"),
    ("/.git/config", "vcs_leak"),
    ("/.DS_Store", "os_metadata"),
)
