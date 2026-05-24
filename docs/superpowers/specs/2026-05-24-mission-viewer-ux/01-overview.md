# Mission Viewer UX — Overview

## Purpose

Five improvements to the Mission Viewer page that make the agent's
thinking and discoveries visible without adding complexity.  Target:
move from 2/10 to 5/10 usability.

## Improvements (ranked by impact)

1. **TurnCard intent** — always show `reason` and `hypothesis`
2. **TurnCard outcome digest** — URL, title, element/network counters
3. **Discovery chips** — routes, assets, candidates below turns
4. **Structured observations** — replace raw JSON with sections
5. **Budget mini-bars** — progress bars for turns/HTTP/browser/inspections

## Data contract

All data comes from existing endpoints — no backend changes.

- `reason` and `hypothesis` are on `AgentAction` (GET /turns/)
- `observations[].data` contains `identity`, `discovered`, `elements`,
  `network`, `cookies`, `console`
- `notes` with `note_type=route/parameter/candidate/gap` for chips
- `mission_budget` + `consumed_budget` on session detail for bars

## Constraints

- All files under 200 lines
- Use design tokens from `tokens.css` (no hardcoded colors)
- CSS modules for styling
- Tests for every new component
