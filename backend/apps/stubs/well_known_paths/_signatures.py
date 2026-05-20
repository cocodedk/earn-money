"""Per-family signature rows for `well_known_paths`.

Each row pins a body / magic-byte signal that distinguishes a real
exposure from a 200-soft-404 / login redirect. Signatures use one of
three pattern types:

* `literal` — substring match (re.escape applied at compile time).
* `regex` — full regex pattern.
* `magic_bytes` — hex-encoded byte prefix; matched against the start
  of the response body.

Spec sources: 1.20-1.25 §Detection logic.
"""
from __future__ import annotations

from ._types import Family, Signature


SIGNATURES_BY_FAMILY: dict[Family, tuple[Signature, ...]] = {
    "env": (
        Signature(
            id="env.kv_line",
            family="env",
            pattern=r"^[A-Z][A-Z0-9_]+=.+$",
            pattern_type="regex",
            case_sensitive=True,
            confidence_hint="high",
            description="One ALL_CAPS=VALUE env line (multiline pattern).",
        ),
        Signature(
            id="env.sensitive_key",
            family="env",
            pattern=r"(?:DB_PASSWORD|STRIPE_KEY|AWS_SECRET|JWT_SECRET|API_KEY|SECRET_KEY)\s*=",
            pattern_type="regex",
            case_sensitive=True,
            confidence_hint="high",
            description="Well-known sensitive key tokens raise severity to medium.",
        ),
    ),
    "git": (
        Signature(
            id="git.head_ref",
            family="git",
            pattern=r"^ref:\s+refs/",
            pattern_type="regex",
            case_sensitive=True,
            confidence_hint="high",
            description="`.git/HEAD` content shape.",
        ),
        Signature(
            id="git.config_ini",
            family="git",
            pattern=r"\[remote \"[^\"]+\"\]\s*\n\s*url\s*=",
            pattern_type="regex",
            case_sensitive=True,
            confidence_hint="high",
            description="`.git/config` remote URL section.",
        ),
        Signature(
            id="git.pack_magic",
            family="git",
            pattern="50 41 43 4b",  # "PACK"
            pattern_type="magic_bytes",
            case_sensitive=True,
            confidence_hint="high",
            description="Git pack file magic bytes.",
        ),
    ),
    "config_files": (
        Signature(
            id="config.spring_datasource",
            family="config_files",
            pattern=r"spring\.datasource\.(?:url|username|password)",
            pattern_type="regex",
            case_sensitive=False,
            confidence_hint="high",
            description="Spring Boot datasource keys.",
        ),
        Signature(
            id="config.rails_database_yml",
            family="config_files",
            pattern=r"^\s*(?:development|production|test):\s*\n\s*adapter:",
            pattern_type="regex",
            case_sensitive=True,
            confidence_hint="high",
            description="Rails database.yml environment + adapter shape.",
        ),
        Signature(
            id="config.docker_compose",
            family="config_files",
            pattern=r"^services:\s*\n",
            pattern_type="regex",
            case_sensitive=True,
            confidence_hint="medium",
            description="docker-compose.yml services root.",
        ),
    ),
    "logs": (
        Signature(
            id="logs.iso8601_level",
            family="logs",
            pattern=r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}.*\b(?:INFO|WARN(?:ING)?|ERROR|DEBUG|TRACE)\b",
            pattern_type="regex",
            case_sensitive=False,
            confidence_hint="high",
            description="ISO-8601 timestamp + log-level token.",
        ),
        Signature(
            id="logs.nginx_combined",
            family="logs",
            pattern=r'^\d+\.\d+\.\d+\.\d+\s+-\s+-\s+\[\d{2}/\w+/\d{4}',
            pattern_type="regex",
            case_sensitive=True,
            confidence_hint="high",
            description="nginx combined-log-format prefix.",
        ),
    ),
    "backup_archives": (
        Signature(
            id="archive.zip",
            family="backup_archives",
            pattern="50 4b 03 04",
            pattern_type="magic_bytes",
            case_sensitive=True,
            confidence_hint="high",
            description="ZIP magic.",
        ),
        Signature(
            id="archive.gzip",
            family="backup_archives",
            pattern="1f 8b",
            pattern_type="magic_bytes",
            case_sensitive=True,
            confidence_hint="high",
            description="gzip magic.",
        ),
        Signature(
            id="archive.7z",
            family="backup_archives",
            pattern="37 7a bc af 27 1c",
            pattern_type="magic_bytes",
            case_sensitive=True,
            confidence_hint="high",
            description="7-Zip magic.",
        ),
        Signature(
            id="archive.rar",
            family="backup_archives",
            pattern="52 61 72 21 1a 07",
            pattern_type="magic_bytes",
            case_sensitive=True,
            confidence_hint="high",
            description="RAR magic.",
        ),
    ),
    "db_dumps": (
        Signature(
            id="db.sql_create_table",
            family="db_dumps",
            pattern=r"(?:^|\n)CREATE TABLE\b",
            pattern_type="regex",
            case_sensitive=False,
            confidence_hint="high",
            description="SQL dump CREATE TABLE statement.",
        ),
        Signature(
            id="db.sql_insert_into",
            family="db_dumps",
            pattern=r"(?:^|\n)INSERT INTO\b",
            pattern_type="regex",
            case_sensitive=False,
            confidence_hint="high",
            description="SQL dump INSERT INTO statement.",
        ),
        Signature(
            id="db.sqlite_magic",
            family="db_dumps",
            pattern="53 51 4c 69 74 65 20 66 6f 72 6d 61 74 20 33 00",
            pattern_type="magic_bytes",
            case_sensitive=True,
            confidence_hint="high",
            description="SQLite 3 file format magic.",
        ),
    ),
}
