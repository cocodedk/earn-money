# Dockerized Env — build plan

Build plan for a Docker Compose scanner platform: the first platform skeleton that can later run cookbook stubs. Build the app foundation only — **do not implement any scanner stub in this work**.

The product stack:

- Django backend (with Django REST Framework)
- React frontend
- Celery worker
- Redis (Celery broker)
- PostgreSQL (durable source of truth)
- Server-Sent Events for live scan updates
- nginx reverse proxy
- Docker Compose ties it together

## Sections

1. [Goal](01-goals.md) — what the local setup must let an operator do
2. [Required services](02-services.md) — per-service responsibilities (backend / frontend / worker / redis / postgres / nginx)
3. [Repo structure](03-repo-structure.md) — suggested directory layout
4. [Backend models](04-backend-models.md) — `Project`, `ScanTarget`, `ScanRun`, `ScanTargetRun`, `ScanEvent`, `Finding`, `Evidence`
5. [API endpoints](05-api-endpoints.md) — REST + SSE
6. [Scan control rules](06-scan-control.md) — state machine: `queued → running → paused → stopping → stopped / failed / done`
7. [Celery task shape](07-celery-task.md) — `run_scan(scan_run_id)` simulator
8. [Frontend pages](08-frontend-pages.md) — Projects / Targets / Scan Runs / Detail / Live Events / Findings / Evidence
9. [Docker requirements](09-docker.md) — `docker compose up --build` + `.env.example`
10. [Security rules](10-security.md) — secrets, exposure, exploit-logic boundary
11. [Acceptance criteria](11-acceptance.md) — what "accepted" means
12. [Keep it small](12-scope.md) — what NOT to build yet

## Where the first stub goes

The first real scanner stub is [`1.1 framework-detection`](../2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/01-framework-detection.md) from the [vuln-scanning cookbook](../2026-05-18-VULN-SCANNING-COOK-BOOK/). The platform skeleton in this spec must be able to run it later, but does not implement it now.

## Relationship to the cookbook shared schema

The Django models in [`04-backend-models.md`](04-backend-models.md) implement what the cookbook expresses logically in [`../2026-05-18-VULN-SCANNING-COOK-BOOK/00-shared-schema.md`](../2026-05-18-VULN-SCANNING-COOK-BOOK/00-shared-schema.md). `ScanTarget` and `Evidence` here add platform plumbing (project / scan_run / finding linkage, `data json`, `method`) on top of the cookbook's logical contract — they're concrete tables, not a rewrite of the shared types. Stub-specific `<Name>Signature` / `<Name>Finding` from cookbook specs will land as additional tables when stubs are implemented.
