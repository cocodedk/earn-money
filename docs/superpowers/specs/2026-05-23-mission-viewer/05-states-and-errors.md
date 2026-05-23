# Mission Viewer — States and Error Handling

## Page-level states

| State | What user sees |
|-------|---------------|
| Loading | "Loading mission..." (via `DetailPageGuard`) |
| Not found | "Mission not found" + back link |
| Backend error | `BackendUnreachableCallout` |
| Session loaded | Top strip + story timeline |

## Timeline states

| State | What user sees |
|-------|---------------|
| No turns yet | "The agent has not started yet." |
| Live / running | Blue pulse dot on latest turn; timeline grows as events arrive |
| Completed | "Mission finished" with outcome summary |
| Failed | "Mission failed" with last error reason |
| Stopped | "Mission stopped" with reason |

## Inline error handling

Turns or notes fetch failure does NOT fail the whole page.  Show an
inline `Callout` in the timeline area: "Could not load turns. Retrying..."
with the session header still visible above.

## Mobile responsive

Top strip wraps to two rows:
- Row 1: mission name + status pill
- Row 2: phase chips + budget counter

Timeline cards stack full-width.  Details disclosure works the same.
