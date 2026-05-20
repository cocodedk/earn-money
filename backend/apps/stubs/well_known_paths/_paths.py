"""Per-family default candidate-path lists for `well_known_paths`.

Each list is the spec's curated set of well-known relative paths to
probe per scan target. Stems / extensions / suffix patterns are kept
as plain strings; the candidate-path resolver layers them onto
`target.base_url`.

Specs:
  1.20 — env files
  1.21 — git metadata
  1.22 — config files
  1.23 — logs
  1.24 — backup archives
  1.25 — exported database files
"""
from __future__ import annotations


ENV_PATHS: tuple[str, ...] = (
    "/.env", "/.env.local", "/.env.dev", "/.env.development",
    "/.env.test", "/.env.testing", "/.env.stage", "/.env.staging",
    "/.env.prod", "/.env.production", "/.env.backup", "/.env.bak",
    "/.env.old", "/.env.save", "/.env.example", "/.env.dist",
    "/.env.sample",
    "/api/.env", "/app/.env", "/backend/.env", "/config/.env",
    "/server/.env",
)


GIT_PATHS: tuple[str, ...] = (
    "/.git/HEAD", "/.git/config", "/.git/index", "/.git/description",
    "/.git/COMMIT_EDITMSG", "/.git/FETCH_HEAD", "/.git/ORIG_HEAD",
    "/.git/packed-refs", "/.git/refs/heads/main",
    "/.git/refs/heads/master", "/.git/objects/info/packs",
    "/.git/logs/HEAD", "/.gitignore", "/.gitattributes",
)


CONFIG_PATHS: tuple[str, ...] = (
    "/config.json", "/config.yaml", "/config.yml",
    "/application.yml", "/application.yaml", "/application.properties",
    "/appsettings.json", "/appsettings.Development.json",
    "/web.config", "/web.xml",
    "/docker-compose.yml", "/docker-compose.yaml",
    "/Dockerfile", "/.dockerignore",
    "/package.json", "/composer.json", "/Gemfile", "/Gemfile.lock",
    "/database.yml", "/secrets.yml", "/settings.py", "/wp-config.php",
)


LOG_PATHS: tuple[str, ...] = (
    "/app.log", "/server.log", "/access.log", "/error.log",
    "/debug.log", "/application.log",
    "/logs/app.log", "/logs/error.log", "/logs/access.log",
    "/log/development.log", "/log/production.log",
    "/laravel.log", "/uwsgi.log", "/nginx-error.log",
    "/wp-content/debug.log",
)


_ARCHIVE_STEMS: tuple[str, ...] = (
    "backup", "archive", "old", "tmp", "_private", "site", "www",
    "html", "public", "app", "wwwroot",
)
_ARCHIVE_EXTS: tuple[str, ...] = (
    ".zip", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz",
    ".txz", ".7z", ".rar", ".gz", ".bz2",
)
ARCHIVE_PATHS: tuple[str, ...] = tuple(
    f"/{stem}{ext}" for stem in _ARCHIVE_STEMS for ext in _ARCHIVE_EXTS
)


_DB_STEMS: tuple[str, ...] = (
    "db", "database", "dump", "backup", "data", "users", "site",
)
_DB_EXTS: tuple[str, ...] = (
    ".sql", ".sql.gz", ".sqlite", ".sqlite3", ".db", ".mdb",
)
DB_DUMP_PATHS: tuple[str, ...] = tuple(
    f"/{stem}{ext}" for stem in _DB_STEMS for ext in _DB_EXTS
)
