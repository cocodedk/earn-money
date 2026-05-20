# Targets page — slice 1 design

**Date:** 2026-05-19
**Owner:** agent-em-frontend
**Reviewer:** codex:rescue (gpt-5.5 xhigh — 2 REJECT rounds, v3 satisfies both)
**Status:** approved by codex's prior conditions; awaiting operator final sign-off
**Implements:** [`docs/superpowers/specs/2026-05-18-MVP-GUI/03-targets.md`](2026-05-18-MVP-GUI/03-targets.md)

## Goal

Build the Targets page (`/targets` and `/targets/new`) so the operator can list and add scan targets. Replaces the two `<ComingSoon name="Targets" />` routes in `App.tsx`. Backend serializer at `backend/apps/targets/serializers.py` (commit `6b9802d`) already accepts host/ip as optional and derives host from `base_url` server-side.

## Scope (locked with operator)

**In:** read (list) + create.

**Out:** edit, retire, delete, target-result page. Deferred until backend exposes `PATCH /api/targets/:id/` and `DELETE /api/targets/:id/`. Spec [`11-api.md`](2026-05-18-MVP-GUI/11-api.md) currently locks only `GET /api/targets/`, `POST /api/targets/`, `GET /api/targets/:id/`.

## Architecture

Single-page slice mirroring the **Projects feature** at `frontend/src/features/projects/`. Two new route components, one new feature directory, one MSW handler addition. No new component primitives — reuses `Table`, `EmptyState`, `Callout`, `PageHeader`, `FormField`, `TextInput`, `Button` from `components/`.

## Files

| File | State | Purpose |
|------|-------|---------|
| `frontend/src/types/api.ts` | modify | Add `Target` and `CreateTargetBody` types |
| `frontend/src/app/routes.ts` | modify | Add `targetsNew: "/targets/new"` |
| `frontend/src/App.tsx` | modify | Swap `<ComingSoon name="Targets" />` for real `TargetsList` and `CreateTarget` |
| `frontend/src/features/targets/api.ts` | new | `useTargetsQuery`, `useCreateTargetMutation`, `TARGETS_KEY` |
| `frontend/src/features/targets/TargetsList.tsx` | new | List page |
| `frontend/src/features/targets/CreateTarget.tsx` | new | Create form page |
| `frontend/src/features/targets/api.test.tsx` | new | Hook tests via MSW |
| `frontend/src/features/targets/TargetsList.test.tsx` | new | List page tests (loading / empty / error / happy) |
| `frontend/src/features/targets/CreateTarget.test.tsx` | new | Form tests (~12 cases — see Tests section) |
| `frontend/src/test/handlers.ts` | no change | Per-test handlers added via `server.use()` (existing pattern; the base file only carries `/api/health/`) |
| `frontend/src/App.e2e.test.tsx` | modify | Extend happy path with targets create |

All new files stay well under the 200-line cap (the Projects analogs sit at 60–90 lines).

## Types

```ts
// types/api.ts — additions
export type Target = {
  id: Uuid;
  project: Uuid;        // FK serialized as bare UUID per 11-api.md
  base_url: string;
  host: string;         // never null; serializer derives from base_url if blank
  ip: string | null;    // serializer normalizes blank → null
  status: TargetStatus; // existing union "active" | "retired"
  created_at: Iso8601;
  updated_at: Iso8601;
};

export type CreateTargetBody = {
  project: Uuid;
  base_url: string;
  host?: string;        // omit when blank; serializer derives
  ip?: string | null;   // omit or null when blank
};
```

## `features/targets/api.ts`

Mirror of `features/projects/api.ts`:

```ts
export const TARGETS_KEY = ["targets"] as const;

export function useTargetsQuery() {
  return useQuery({
    queryKey: TARGETS_KEY,
    queryFn: () => http<Paginated<Target>>("/api/targets/"),
  });
}

export function useCreateTargetMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateTargetBody) =>
      http<Target>("/api/targets/", { method: "POST", body }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: TARGETS_KEY });
    },
  });
}
```

## `TargetsList.tsx`

**Columns:** Base URL · Host · IP · Project · Status · Created at.

**Project name join:** look up `target.project` via cached `useProjectsQuery()`. Render the project's `name` if found; render `target.project.slice(0, 8)` as a fallback (covers race where a project was deleted out from under a target). Zero extra requests in the common case — the Projects query is already cached by TanStack Query.

**IP cell:** render `target.ip ?? "—"` so the empty case has a visual mark.

**Status badge:** simple coloured pill — `active = green`, `retired = gray`. (14-styling.md doesn't define TargetStatus colours explicitly; these track ScanRunStatus's `done = green` / `stopped = gray` convention.)

**Actions column:** dropped for slice 1. No Edit/Retire/Delete, target-result page is `<ComingSoon />`. Cleaner than rendering empty cells.

**Branches:**
- loading → `TableSkeleton` (already wired in `Table`)
- empty → `EmptyState` with "No targets yet." + Create-target action button navigating to `/targets/new`
- error → `Callout variant="error" title="Backend unreachable"` with Retry button calling `query.refetch()`. Matches `ProjectsList`.
- happy → table rows

## `CreateTarget.tsx`

**Fields:**

| Field | UI | Required | Notes |
|-------|----|----------|-------|
| Project | `<select>` populated from `useProjectsQuery` | yes | Disabled when projects-query is loading, errored, or returned empty. See "Project select states" below. |
| Base URL | `<TextInput>` | yes | Trimmed on submit. Authority validation — see "Base URL validation" below. |
| Host | `<TextInput>` | no | Helper text: "Leave blank to auto-derive from base URL". |
| IP | `<TextInput>` | no | Helper text: "Leave blank if unknown". |
| Status | — | — | Not in form. Backend defaults to `"active"`. Out of scope for this slice; retire is a future PATCH. |

**Project select states:**
- Loading → disabled select, placeholder "Loading projects…"
- Error → disabled select, `Callout variant="error"` "Could not load projects" + Retry
- Empty list → disabled select, `Callout` linking to `/projects/new`: "Create a project first."
- Loaded → enabled select with `<option value={p.id}>{p.name}</option>` rows; placeholder option "Select a project…" with `value=""`.

**Base URL validation pipeline (client-side, on submit, in order):**

```ts
const value = baseUrl.trim();
if (!value) → field error "base_url is required";
if (!/^https?:\/\/[^\/\s]+/i.test(value)) →
    field error "base_url must start with http:// or https:// and include a host";
try {
  const parsed = new URL(value);
  if (parsed.hostname === "") → field error "Enter a valid URL like https://example.com";
} catch {
  → field error "Enter a valid URL like https://example.com";
}
```

The regex requires at least one non-slash non-whitespace character immediately after `://`, so it rejects:
- `https:` (no slashes)
- `https://` (no authority)
- `https:// ` (whitespace authority)
- `https:///path` (empty authority, three slashes)
- `https:////x` (empty authority, four slashes)

The `new URL()` parse is a defensive backstop — WHATWG URL parsing can normalize edge cases (e.g. `https:///path` may parse with `hostname = "path"` in some engines), so both checks run.

**Error flow:** field-level (DRF `{field: [...]}`), non-field (`{non_field_errors: [...]}`), 4xx detail (`{detail: ...}`), 5xx, and network failure all flow through the existing `parseApiError` helper, exactly like `CreateProject`.

**On success:** `navigate(ROUTES.targets)`.

## Tests

**`api.test.tsx`** (~3 cases):
- happy: list query resolves and returns `results`
- happy: create mutation POSTs and invalidates the list cache (verify via re-fetch)
- transport error surfaces as `HttpError`

**`TargetsList.test.tsx`** (~5 cases):
- loading → renders TableSkeleton
- empty → renders EmptyState with Create-target button; clicking it navigates to `/targets/new`
- error → renders Backend-unreachable Callout; Retry triggers refetch
- happy → renders rows with project name resolved from cached useProjectsQuery
- happy with unknown project id → renders short-UUID fallback

**`CreateTarget.test.tsx`** (~12 cases — these are what codex required):
- happy submit (all fields filled) → navigates to `/targets`
- happy submit with blank host/ip → backend response shows host derived
- projects query loading → select disabled, placeholder "Loading projects…"
- projects query error → Callout shown, select disabled
- projects query returns empty list → disabled select, Create-project link visible
- base_url empty → field error "base_url is required", no network call
- base_url `"not-a-url"` → field error scheme/host, no network call
- base_url `"https://"` (empty authority) → field error, no network call
- base_url `"https:// "` (whitespace authority) → field error, no network call
- base_url `"https:///path"` (three slashes) → field error, no network call
- project field server error (stale UUID, 400 with `{project: ["..."]}`) → project FormField shows the field error
- network failure on submit → banner "Backend unreachable."

For the "no network call" assertions, use an MSW request counter shared with each test (reset in `beforeEach`).

**MSW handlers** added per-test via `server.use(...)` (the project's existing pattern; `test/handlers.ts` only carries `/api/health/`):
- `GET /api/targets/` → paginated list (configurable per-test)
- `POST /api/targets/` → 201 with body echo (configurable to return 400 with field errors)
- `GET /api/projects/` for the CreateTarget cases that override the projects-query state

**`App.e2e.test.tsx`** extension: after the existing Projects happy-path, navigate to `/targets`, click Create target, fill form with `project = newly-created-project.id`, `base_url = "https://dvwa.cocode.dk"`, submit, assert the target row appears in the list with project name resolved.

## Acceptance criteria

- All branches above covered by tests.
- 100% line + branch coverage on the new files (project's existing threshold).
- `npm run typecheck`, `npm run lint`, `npm test`, `npm run build` all green.
- Operator can: open `/targets` → click Create target → pick a project → enter `https://dvwa.cocode.dk` (host/ip blank) → submit → see the row in the list with host `dvwa.cocode.dk` and ip `—`.
- No file exceeds 200 lines.
- `/simplify` round returns no actionable findings after final commit.

## Out of scope (this slice)

- Edit target / Retire target / Delete target — wait for backend PATCH/DELETE.
- Target-result page — separate spec at [`07-target-result.md`](2026-05-18-MVP-GUI/07-target-result.md), still `<ComingSoon />` for now.
- Server-side filtering, search, or sort. The page renders the first 50 targets per DRF default pagination; pagination UI is a future slice.
- Bulk add (paste a list of URLs). Single-target form only.
- Backend denormalization of `project_name` onto the Target row.

## Open questions for the operator

None — both scope decisions and codex's two REJECT rounds have been resolved.
