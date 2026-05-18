# 11. API integration

Contract locked between agent-em-frontend and agent-em-backend on 2026-05-18.

## Conventions

| Concern | Rule |
|---------|------|
| Base prefix | `/api/` |
| Trailing slash | Always present (DRF default) |
| IDs | UUIDv4 plain strings; FKs serialize as the related row's UUID, never as nested objects. For nested reads, request a future `?include=…` extension. |
| Timestamps | ISO-8601 UTC with microseconds, e.g. `2026-05-18T20:45:30.126602Z`. |
| Pagination | DRF `PageNumberPagination` on all list endpoints. Response: `{count, next, previous, results}`. Query: `?page=N&page_size=N`. Default page size 50. |
| Error: 400 validation | `{"<field>": ["msg", …]}` per field OR `{"non_field_errors": ["msg", …]}` for cross-field. |
| Error: other 4xx | `{"detail": "…"}`. |
| Error: 5xx | Generic; frontend renders a hard-coded message. |
| Network failure | No response at all; frontend renders "Backend unreachable". |
| CORS | Origins from `CORS_ALLOWED_ORIGINS` env var. |
| Auth | None in MVP. |

## Vocabularies

```ts
type ScanRunStatus = "queued" | "running" | "paused" | "stopping" | "stopped" | "failed" | "done";
type TargetStatus  = "active" | "retired";
type Severity      = "info" | "low" | "medium" | "high" | "critical";
```

All three are emitted as lowercase strings from DRF serializers and treated as exhaustive enums on the frontend.

## Denormalized fields

`GET /api/projects/` MUST include `target_count` and `scan_run_count` on each row, annotated via `Count("targets")` and `Count("scan_runs")` on the queryset. The frontend MUST NOT fan out per project to compute these.

## Endpoints

```text
GET    /api/projects/
POST   /api/projects/
GET    /api/projects/:id/

GET    /api/targets/
POST   /api/targets/
GET    /api/targets/:id/

GET    /api/stubs/
GET    /api/stubs/:slug/

GET    /api/scan-runs/
POST   /api/scan-runs/
GET    /api/scan-runs/:id/

POST   /api/scan-runs/:id/start/
POST   /api/scan-runs/:id/pause/
POST   /api/scan-runs/:id/resume/
POST   /api/scan-runs/:id/stop/

GET    /api/scan-runs/:id/events/
GET    /api/scan-runs/:id/findings/
GET    /api/scan-runs/:id/evidence/

GET    /api/findings/
GET    /api/findings/:id/

GET    /api/evidence/
GET    /api/evidence/:id/

GET    /sse/scan-runs/:id/events/

GET    /api/health/        # {status, db} for slice 1; {status, db, redis, worker, version} once Settings page lands
```
