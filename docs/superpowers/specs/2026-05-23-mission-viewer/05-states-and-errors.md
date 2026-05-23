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
| Failed | "Mission failed" with reason when provided, otherwise generic copy |
| Stopped | "Mission stopped" with reason when provided, otherwise generic copy |
| Truncated turns | Timeline plus "Showing first N turns" hint when `next !== null` |
| Truncated notes | Inline notes plus "Some notebook entries are hidden" hint when `next !== null` |

## Inline error handling

Turns or notes fetch failure does NOT fail the whole page.  Show an
inline `Callout` in the timeline area: "Could not load turns. Retrying..."
with the session header still visible above.

Budget data is optional.  If `mission_budget.max_turns` is absent, show
only "`N` turns used"; if consumed turns are absent, show "0 turns used"
until turns or budget data arrives.

## Mobile responsive

Top strip wraps to two rows:
- Row 1: mission name + status pill
- Row 2: phase chips + budget counter

Timeline cards stack full-width.  Details disclosure works the same.

## Accessibility

- Status icons have text labels or `aria-label`; color is not the only
  signal.
- Details disclosures are keyboard reachable and expose expanded state.
- Sticky strip content remains readable at 320 px width without
  horizontal scrolling.
