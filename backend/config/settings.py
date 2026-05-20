"""Django settings — local-dev profile.

Reads env vars from the process environment (set in docker-compose.yml
from the .env file). No secrets baked in; the operator's .env is the
single source of truth at runtime.
"""
from __future__ import annotations

import os
from pathlib import Path

import dj_database_url


BASE_DIR = Path(__file__).resolve().parent.parent


# --- Security ---
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-fallback")
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]


# --- Apps ---
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    # Cookbook scanner platform apps
    "apps.common",
    "apps.projects",
    "apps.targets",
    "apps.scans",
    "apps.events",
    "apps.findings",
    "apps.evidence",
    "apps.stubs",
]


MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "config.urls"


TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# --- Database ---
DATABASES = {
    "default": dj_database_url.config(
        default=os.environ.get(
            "DATABASE_URL",
            "postgres://scanner:scanner@postgres:5432/scanner",
        ),
        conn_max_age=600,
    )
}


# --- Cache / Celery ---
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.environ.get(
    "CELERY_RESULT_BACKEND", "redis://redis:6379/1"
)
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 60 * 30


# --- Internationalization ---
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# --- Static ---
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"


# --- CORS ---
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ALLOWED_ORIGINS", "http://localhost,http://localhost:5173"
    ).split(",")
    if origin.strip()
]


# --- DRF defaults ---
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_PAGINATION_CLASS": "config.pagination.DefaultPagination",
    "PAGE_SIZE": 50,
}


# --- Misc ---
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Cookbook tree (read-only file source for the Stubs API) ---
# Mounted into the backend container at /cookbook (see docker-compose.yml).
COOKBOOK_ROOT = os.environ.get("COOKBOOK_ROOT", "/cookbook")


# --- App version (surfaced by /api/health/) ---
# Set in compose / deployment. Use git SHA or release tag in production.
APP_VERSION = os.environ.get("APP_VERSION", "dev")
