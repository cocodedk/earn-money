# 11. Acceptance criteria

The setup is accepted when:

```text
docker compose up --build works
Django migrations run
React dashboard loads
backend health endpoint works
a project can be created
targets can be created
a scan run can be created
scan can be started
scan can be paused
scan can be resumed
scan can be stopped
worker writes scan events
frontend shows live scan events
statuses persist in PostgreSQL
no real scanner stub is implemented yet
```
