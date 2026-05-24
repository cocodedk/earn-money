# Improvement 4 — Structured Observation Details

## What changes

Inside the expanded TurnCard Details panel, replace the raw JSON dump
with structured sections.  Keep raw JSON as a disclosure at the bottom.

## Sections (rendered when data is present)

| Section | Data path | Render |
|---------|-----------|--------|
| Page | `identity.url`, `identity.title`, `identity.status_code` | URL + title + status |
| Routes | `discovered.routes` | Bulleted list |
| Assets | `discovered.assets` | Bulleted list |
| Network | `network` | Count + "Show requests" disclosure with table (method, url, status) |
| Elements | `elements.forms/links/inputs/buttons` | Inline counts: "3 forms · 12 links · 5 inputs · 2 buttons" |
| Cookies | `cookies` | Count + disclosure with name/domain list |
| Action | `action_type`, `validation_status`, `execution_status` | Existing action lines |
| Tokens | `input_tokens`, `output_tokens` | Existing token line |
| Raw JSON | full `observations[].data` | Collapsed disclosure at bottom |

## Sections are skipped when empty

If `discovered.routes` is an empty array, skip the Routes section.
If no observations exist, show only Action/Tokens/Time.

## Tests

- Expand details with page observation → shows Page section with URL
- Expand details with 3 routes → shows Routes section with 3 items
- Expand details with network → shows "52 requests" + disclosure
- Expand details with no observations → shows only action/tokens
- Raw JSON disclosure exists and renders valid JSON
