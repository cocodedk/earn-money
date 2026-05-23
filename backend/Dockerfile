# Cookbook scanner platform — Django backend image.
# Used by both `backend` (Django runserver) and `worker` (Celery) services.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build deps for psycopg + general tooling. `tzdata` so the TZ env
# var (Europe/Copenhagen by default — set in docker-compose.yml) is
# resolvable by Python's zoneinfo and C's localtime().
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev curl tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/
RUN pip install -r requirements.txt
RUN playwright install --with-deps chromium

COPY . /app/

EXPOSE 8000

# Default — runserver. The `worker` service overrides this with the
# celery command in docker-compose.yml.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
