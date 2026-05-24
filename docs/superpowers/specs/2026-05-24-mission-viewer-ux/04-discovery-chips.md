# Improvement 3 — Discovery Chips

## What changes

Below relevant turns, render small colored chips showing what the
agent discovered.  Grouped by type, capped at 3 visible with "+N more"
expandable.

## Data sources

Two sources, merged per turn:

1. **Notes** — `AgentNote` with `note_type` in
   `route | parameter | candidate | gap`.  Content has a `text` field
   or a structured object with `route`, `status`, etc.

2. **Observation discoveries** — from `observations[0].data.discovered`:
   - `routes`: array of route strings
   - `assets`: array of asset URLs/paths

## Chip types and colors

| Source | Chip label | Token |
|--------|-----------|-------|
| note: route | `route /path` | `--accent` |
| note: parameter | `param name` | `--info` |
| note: candidate | `candidate: text` | `--warn` |
| note: gap | `gap: text` | `--err` |
| discovered route | `route /path` | `--accent` |
| discovered asset | `asset filename` | `--info` |

## Layout

Chips appear in a flex row below the turn card, left-aligned, with
small gap.  Max 3 visible.  If more, show a "+N more" chip that
expands the rest.

## Dedup

Routes from notes and observation discoveries may overlap.  Dedup by
value — prefer the note version (has richer context).

## Tests

- Render turn with 2 route notes → 2 route chips shown
- Render turn with 5 discovered routes → 3 chips + "+2 more"
- Click "+2 more" → all 5 visible
- Render turn with no notes and no discoveries → no chips section
- Render turn with candidate note → chip uses warn color
