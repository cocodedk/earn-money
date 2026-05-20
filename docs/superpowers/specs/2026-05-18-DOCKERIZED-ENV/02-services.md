# 2. Required services

Create this Docker Compose setup:

```yaml
services:
  backend
  frontend
  worker
  redis
  postgres
  nginx
```

## backend

Django app.

Responsibilities:

* REST API
* auth-ready structure
* project management
* target management
* scan run management
* scan control commands
* SSE stream endpoint
* database migrations

## frontend

React app.

Responsibilities:

* dashboard UI
* call backend API
* show projects
* show targets
* show scan runs
* start/pause/stop scan buttons
* live event view using SSE

Use Vite unless the repo already uses another React setup.

## worker

Celery worker.

Responsibilities:

* run scan jobs
* read scan state
* emit scan events
* respect pause and stop requests

Do not kill jobs for pause.

Use cooperative control.

The worker must check scan state between steps.

## redis

Use Redis for:

* Celery broker
* Celery result backend, if needed
* short-lived scan control signals, if useful

PostgreSQL remains the source of truth.

## postgres

Use PostgreSQL for durable data:

* projects
* targets
* scan runs
* scan target runs
* scan events
* findings
* evidence

## nginx

Use nginx as reverse proxy.

Routes:

```text
/        -> frontend
/api/    -> backend
/sse/    -> backend SSE endpoint
/admin/  -> Django admin
```
