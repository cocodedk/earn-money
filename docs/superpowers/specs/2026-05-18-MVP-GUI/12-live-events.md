# 12. Live events

Use Server-Sent Events.

## Frontend behaviour

```text
open EventSource when scan detail page loads
append each event to the live event list
show connection status
reconnect if disconnected
fall back to polling if SSE fails
```

## SSE message shape

```json
{
  "id": "event-uuid",
  "scan_run_id": "scan-run-uuid",
  "target_id": "target-uuid",
  "level": "info",
  "event_type": "target_started",
  "message": "Started target https://dvwa.cocode.dk",
  "data": {},
  "created_at": "datetime"
}
```
