# Mission Viewer Backend — Spec Overview

Four backend pieces needed for the V3 mission viewer frontend:

1. [REST API](01-rest-api.md) — AgentSession create/list/retrieve + nested turns/notes
2. [Start Mission](02-start-mission.md) — POST endpoint + Celery task + lifecycle management
3. [SSE & Event Enrichment](03-sse-enrichment.md) — Generic SSE frames + rich agent event payloads
4. [Runtime Dependencies](04-runtime-deps.md) — Playwright, anthropic, openai in requirements + Dockerfile

All files follow existing backend conventions: DRF serializers/viewsets,
DefaultRouter registration, Celery tasks via `transaction.on_commit`, and
append-only Event rows as the source for both REST event history and SSE.
