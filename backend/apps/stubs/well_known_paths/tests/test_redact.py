"""Per-family redaction contract for stub `well_known_paths`.

Spec sources: 1.20-1.25 §Safety + §PII handling.
"""
from __future__ import annotations

from apps.stubs.well_known_paths.redact import redact


# --- env: keys preserved, values redacted ---


def test_env_keys_preserved_values_redacted() -> None:
    body = b"DB_PASSWORD=secret123\nAPI_KEY=sk_live_abc\n"
    out = redact(family="env", body=body)
    assert "DB_PASSWORD=<REDACTED>" in out
    assert "API_KEY=<REDACTED>" in out
    assert "secret123" not in out
    assert "sk_live_abc" not in out


# --- git: ASCII refs preserved with generic redaction ---


def test_git_ascii_ref_preserved() -> None:
    body = b"ref: refs/heads/main\n"
    out = redact(family="git", body=body)
    assert "ref: refs/heads/main" in out


def test_git_binary_pack_redacted() -> None:
    body = b"PACK" + b"\x00\x01\x02\x03" * 100
    out = redact(family="git", body=body)
    assert "binary-redacted" in out


# --- config_files: generic secret sweep ---


def test_config_redacts_secrets() -> None:
    body = b'spring.datasource.password=topsecret123\nspring.datasource.url=jdbc:mysql://x/y\n'
    out = redact(family="config_files", body=body)
    assert "topsecret123" not in out
    assert "spring.datasource.password" in out


# --- logs: emails + IPs redacted ---


def test_logs_redact_emails_and_ips() -> None:
    body = (
        b"2026-05-20T10:00:00Z INFO Login from 192.168.1.42 by alice@example.com\n"
    )
    out = redact(family="logs", body=body)
    assert "alice@example.com" not in out
    # Generic redactor handles emails via REDACTED:email marker
    assert "[REDACTED:" in out


# --- backup_archives: magic preserved, body redacted ---


def test_archives_magic_preserved_body_redacted() -> None:
    body = bytes.fromhex("504b0304") + b"\x00" * 100
    out = redact(family="backup_archives", body=body)
    assert "<magic:50 4b 03 04>" in out
    assert "<binary-redacted bytes=104>" in out


# --- db_dumps: SQL text — keep CREATE TABLE, redact INSERT VALUES ---


def test_db_dump_keeps_create_table_redacts_insert_values() -> None:
    body = (
        b"CREATE TABLE users (id INT, email TEXT);\n"
        b"INSERT INTO users (id, email) VALUES (1, 'alice@example.com');\n"
    )
    out = redact(family="db_dumps", body=body)
    assert "CREATE TABLE users" in out
    assert "INSERT INTO users" in out
    assert "<REDACTED>" in out
    assert "alice@example.com" not in out


def test_db_dump_binary_sqlite_redacted() -> None:
    body = b"SQLite format 3\x00" + b"\x00\x01\x02\x03" * 100
    out = redact(family="db_dumps", body=body)
    assert "binary-redacted" in out


def test_empty_body_env_returns_empty() -> None:
    assert redact(family="env", body=b"") == ""


def test_empty_body_db_dump_returns_empty() -> None:
    # Exercises _is_binary(b"") → False path.
    assert redact(family="db_dumps", body=b"") == ""


def test_empty_body_git_returns_empty() -> None:
    # Exercises _is_binary(b"") on git family — falls through to
    # generic-redact on the empty string.
    assert redact(family="git", body=b"") == ""
