# 21. Current project (frontend-only)

The "current project" shown in the top bar and used as the default project for new scan runs is a **frontend-only** concept. The backend has no session state for MVP — every API call is independent. See `11-api.md` for the agreed contract.

## Storage

| Key | Value |
|-----|-------|
| `em.frontend.currentProjectId` | UUIDv4 string, or `null` if not set |

Stored in `window.localStorage`. Survives reload. Per-browser, not per-user (no auth in MVP).

## Hook

```ts
function useCurrentProject(): {
  id: string | null;
  setId: (id: string | null) => void;
  project: Project | null;   // resolved from useProjectsQuery; null while loading or if id no longer exists
}
```

- On mount: reads the key. If `id` doesn't match any project in the cached projects list, clears the key.
- On `setId`: writes the key and dispatches a `storage` event so other tabs sync.
- On project deletion via mutation: invalidates the projects query; the hook detects the missing id on the next read and clears.

## Surfaces

- **Top bar**: `<CurrentProjectChip>` renders the project name + a "switch" button that opens the projects list. If no current project, renders "(no project selected)".
- **Create scan run page** (later slice): pre-selects the current project.
- **Filter defaults** on `/findings`, `/evidence`, `/scan-runs` (later slices): default `project=<currentProjectId>` if set.

## Reset rules

- Project deleted server-side → key cleared on next list refresh.
- Operator selects a different project → key updated.
- Operator clears it explicitly → key set to `null`.
- Manual `localStorage.clear()` → next mount reads `null`, no error.

## Test handles

- `data-testid="current-project-chip"` on the top-bar chip.
- `data-testid="current-project-switch"` on the switch button.
