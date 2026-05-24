# Improvement 5 — Budget Mini-Bars

## What changes

Replace the single "8 of 25 turns used" text in MissionStrip with
3-4 tiny labeled progress bars showing multiple budget dimensions.

## Bars to show

| Label | Used | Max | Data |
|-------|------|-----|------|
| Turns | `consumed_budget.mission.turns` | `mission_budget.max_turns` | session detail |
| HTTP | `consumed_budget.mission.http_requests` | `mission_budget.max_http_requests` | session detail |
| Browser | `consumed_budget.mission.browser_actions` | `mission_budget.max_browser_actions` | session detail |
| Inspections | `consumed_budget.mission.asset_inspections` | `mission_budget.max_asset_inspections` | session detail |

## Render rules

- Only show bars where `max` is defined in `mission_budget`
- If no max for a dimension, skip that bar
- Bar fill: percentage = used / max, capped at 100%
- Color: `--ok` for < 75%, `--warn` for 75-90%, `--err` for > 90%
- Label format: "Turns 8/25" below each bar
- Budget overlay from SSE updates the used values optimistically

## Layout

Horizontal row of mini-bars, each ~60px wide.  On mobile, wrap to
second line.

## Tests

- Session with max_turns=25, used=8 → bar at 32%, green
- Session with max_turns=25, used=20 → bar at 80%, yellow
- Session with max_turns=25, used=24 → bar at 96%, red
- Session with no max_http_requests → HTTP bar hidden
- Budget overlay updates bar values
