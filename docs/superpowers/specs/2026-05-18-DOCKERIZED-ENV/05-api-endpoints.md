# 5. API endpoints

Create these endpoints.

```text
GET    /api/projects/
POST   /api/projects/
GET    /api/projects/{id}/

GET    /api/targets/
POST   /api/targets/
GET    /api/targets/{id}/

GET    /api/scan-runs/
POST   /api/scan-runs/
GET    /api/scan-runs/{id}/

POST   /api/scan-runs/{id}/start/
POST   /api/scan-runs/{id}/pause/
POST   /api/scan-runs/{id}/resume/
POST   /api/scan-runs/{id}/stop/

GET    /api/scan-runs/{id}/events/
GET    /api/scan-runs/{id}/findings/
GET    /api/scan-runs/{id}/evidence/

GET    /sse/scan-runs/{id}/events/
```

The SSE endpoint streams new `ScanEvent` records.

Keep it simple.

Polling fallback is acceptable.
