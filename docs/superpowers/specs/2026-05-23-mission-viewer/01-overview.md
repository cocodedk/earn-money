# Mission Viewer — Overview

## Purpose

A real-time page where the operator watches the V3 LLM agent work a
mission turn-by-turn.  The design goal is "a kid can understand it":
one scrolling story, plain-language descriptions, no dashboard jargon.

Persisted REST data is the source of truth.  SSE is used only to make
the page feel live: it invalidates queries and temporarily overlays the
budget counter between session refetches.

## Route

`/missions/:sessionId` — read-only viewer.  No list page or nav entry
in this slice.  Linked from the Start Mission flow on the targets /
scan-runs pages.

## Visual zones

1. **Top strip** (sticky, low height)
   - Left: mission profile name + target host + session status pill
   - Centre: phase chips rendered from `active_phases` (backend), current
     phase highlighted
   - Right: budget counter — "8 of 25 turns used"; cost/tokens in
     tooltip only; degrades to "8 turns used" if limit is absent

2. **Story timeline** (main body, single column)
   - Turn cards in ascending order (oldest top, newest bottom)
   - Each card: status icon + one plain-language sentence + phase badge +
     relative timestamp
   - Collapsible "Details" disclosure: action args, observation JSON,
     tokens, raw event data, exact timestamp
   - Inline notebook entries below the turn that created them

## What this page does NOT do

- Start missions (that is a POST from another page)
- Show a sidebar, multi-panel layout, or permanent notes panel
- Display JSON, UUIDs, or token counts by default
- Treat SSE events as canonical turn data

## Acceptance criteria

- Direct navigation to `/missions/<session-id>` loads the mission from
  the session endpoint and renders the top strip plus story timeline.
- A non-technical viewer can understand each visible turn from the
  default card text without opening Details.
- Technical data remains available in Details without appearing in the
  default view.
- Terminal missions show a clear final state and stop live updates.
