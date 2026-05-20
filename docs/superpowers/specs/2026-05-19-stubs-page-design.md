# Stubs page — slice 1 design

**Date:** 2026-05-19
**Owner:** agent-em-frontend
**Reviewer:** agent-em-backend (ACCEPT, two micro-nits folded in)
**Status:** approved by peer; operator delegated approval
**Implements:** [`docs/superpowers/specs/2026-05-18-MVP-GUI/04-stubs.md`](2026-05-18-MVP-GUI/04-stubs.md)

## Goal

Build the read-only Stubs pages: `/stubs` (list of all 278 cookbook stubs) and `/stubs/:slug` (per-stub detail with markdown body). Replaces the `<ComingSoon name="Stubs" />` route in `App.tsx`.

## Backend (no changes)

`backend/apps/stubs/views.py` already serves:

- `GET /api/stubs/` → **bare array** (no DRF pagination — 278 items fit; frontend filters client-side). No `body` field on list items.
- `GET /api/stubs/<phase.spec>/` → same shape **plus `body`** markdown. `lookup_value_regex = r"\d+\.\d+"` accepts the dot in the composite slug. 404 if slug is unknown.

Stub item shape (from `backend/apps/stubs/registry.py:96-108`):

```
slug          "1.1"                       composite id, the URL slug
phase         1                            int
spec          1                            int
phase_slug    "01-information-gathering"   dir name
spec_slug     "framework-detection"        kebab-case label from frontmatter
title         "Framework detection"        from "# 1.1 Framework detection" body header
phase_title   "Information gathering"      from blockquote breadcrumb
category      "Content discovery"          ditto, may be empty
status        "pending" | "in-progress" | "blocked" | "done"
fixture       "juice-shop" | "tbd" | ...
path          "01-information-gathering/01-framework-detection.md"
body          "<full markdown>"            detail only
```

Peer-confirmed: status vocabulary is **closed** to the 4 values above; today only `pending` and `done` are emitted across all 278 specs. Backend has no changes planned that would break this design.

## Scope

**In:** read (list + detail). **Out:** "Create scan run for this stub" action (Scan Runs page is still `<ComingSoon />` — a button would dead-end). The backend endpoint `POST /api/scan-runs/` already exists but the picker UI doesn't. Defer to the Scan Runs slice.

Markdown body is rendered as monospace `<pre>` per `14-styling.md` ("monospace blocks for JSON and raw excerpts"). **No markdown-renderer dependency** added — cookbook bodies are operator-facing documentation, YAGNI until users complain.

## Architecture

Mirrors the established Projects/Targets feature shape with two adaptations: (1) hooks return a bare array, not `Paginated<T>`, and (2) a per-id detail query is added (Projects/Targets only have list+create today).

## Files

| File | State | Purpose |
|------|-------|---------|
| `frontend/src/types/api.ts` | modify | Add `StubStatus`, `StubSummary`, `Stub` |
| `frontend/src/app/routes.ts` | modify | Add `stubDetail: "/stubs/:slug"` |
| `frontend/src/App.tsx` | modify | Swap `<ComingSoon name="Stubs" />` for real routes |
| `frontend/src/features/stubs/api.ts` | new | `useStubsQuery`, `useStubQuery(slug)`, `STUBS_KEY` |
| `frontend/src/features/stubs/StubsList.tsx` | new | List page |
| `frontend/src/features/stubs/StubDetail.tsx` | new | Detail page |
| `frontend/src/features/stubs/*.test.tsx` | new | Vitest + MSW per feature file |
| `frontend/src/test/helpers.tsx` | modify | Add `withBareArray(path, rows)` to complement `withPaginated` |
| `frontend/src/App.e2e.test.tsx` | modify | Extend with stubs list → detail → back flow |

All new files target the 200-line cap. Markdown body length is variable; `StubDetail.tsx` itself stays tiny because the body is rendered as one `<pre>` block.

## Types

```ts
export type StubStatus = "pending" | "in-progress" | "blocked" | "done";

export type StubSummary = {
  slug: string;         // "<phase>.<spec>", composite id and URL slug
  phase: number;
  spec: number;
  phase_slug: string;
  spec_slug: string;
  title: string;
  phase_title: string;
  category: string;
  status: StubStatus;
  fixture: string;
  path: string;
};

export type Stub = StubSummary & { body: string };
```

## `features/stubs/api.ts`

```ts
export const STUBS_KEY = ["stubs"] as const;
export const stubKey = (slug: string) => [...STUBS_KEY, slug] as const;

export function useStubsQuery() {
  return useQuery({
    queryKey: STUBS_KEY,
    queryFn: () => http<StubSummary[]>("/api/stubs/"),
  });
}

export function useStubQuery(slug: string | undefined) {
  return useQuery({
    queryKey: stubKey(slug ?? ""),
    queryFn: () => http<Stub>(`/api/stubs/${slug}/`),
    enabled: Boolean(slug),
  });
}
```

No mutations. List returns bare array; detail returns full `Stub`.

## `StubsList.tsx`

**Columns:** Phase · Spec · Slug · Title · Status · Fixture · Actions.

The **Slug cell** is a `<Link to={\`/stubs/${slug}\`}>` (peer-suggested ergonomics) — bigger click target, keyboard-discoverable via the explicit Actions button.

The **Actions cell** has a single `<ButtonLink to={\`/stubs/${slug}\`}>View</ButtonLink>`.

The **Status badge** palette (peer-tuned):

| Status | Colour |
|--------|--------|
| `done` | green (matches the 14-styling `done=green` convention) |
| `in-progress` | blue (matches `running=blue`) |
| `blocked` | **amber/orange** (peer micro-nit: reserves red for hard failures) |
| `pending` | gray (matches `queued=gray`) |

Inline badge — single consumer, doesn't justify a new primitive (same call as the Targets slice).

**Branches:**
- loading → `TableSkeleton`
- error → `Callout` "Backend unreachable" with Retry
- empty → `EmptyState` "No stubs found." (no Create action — stubs are file-backed, not creatable from UI)
- happy → table

## `StubDetail.tsx`

Loads from `useStubQuery(slug)`. Branches:

- loading → `TableSkeleton`-equivalent or a small spinner row
- 404 (HttpError with `response.status === 404`) → `Callout` variant info "Stub not found." + link back to `/stubs`
- other error → `Callout` variant error "Backend unreachable" + Retry
- happy →
  - `PageHeader` title = `<phase.spec> · <title>` (e.g. "1.1 · Framework detection")
  - Metadata table: phase title, category, fixture, status (badge), path
  - Markdown body rendered as `<pre className="whitespace-pre-wrap font-mono ...">` per 14-styling

Empty `spec_slug` shows as `—` (peer-confirmed acceptable; rare in practice — zero specs have empty `slug:` today).

Useful aria: the `<pre>` carries `role="article"` so screen readers traverse it as one block.

## Tests

**`api.test.tsx`** (~3 cases):
- `useStubsQuery` resolves a bare array
- `useStubQuery` resolves a Stub by slug
- `useStubQuery` is disabled when slug is undefined (no network call)

**`StubsList.test.tsx`** (~5 cases):
- loading → skeleton
- empty → empty state (no Create action)
- error → Backend-unreachable Callout with Retry
- happy → rows; each status renders the correct badge palette; slug cell is a link
- click slug-link → navigates to `/stubs/:slug` (LocationProbe)

**`StubDetail.test.tsx`** (~5 cases):
- loading → skeleton/spinner
- 404 (backend returns 404) → "Stub not found." + back-link to /stubs
- transport error → Backend-unreachable Callout
- happy → metadata header + markdown body in a `<pre>`
- happy with empty `spec_slug` → `—` rendered

**`App.e2e.test.tsx`** extension:
- Render `<App />` at `/stubs`. MSW returns one stub. Click slug-link. Assert detail page renders the body. Click back to `/stubs`. Assert list shown.

## Helpers

Add `withBareArray(path, rows)` to `frontend/src/test/helpers.tsx` (next to the existing `withPaginated`):

```ts
export function withBareArray(path: string, rows: unknown[]) {
  server.use(msw.get(path, () => HttpResponse.json(rows)));
}
```

Used by the new stubs tests.

## Acceptance criteria

- All branches covered by tests.
- 100% line + branch coverage on new files.
- `npm test`, `npm run build` green.
- Operator can: open `/stubs` → see 278+ rows after backend mount stabilises → click any slug → see the rendered detail with body → click back-link → return to list.
- No file exceeds 200 lines.
- `/simplify` round returns no actionable findings.

## Out of scope

- "Create scan run for this stub" action (deferred until Scan Runs slice).
- Markdown-to-HTML rendering (no dep added).
- Server-side search / phase filter UI (operator-friendly client-side filter can land in slice 2).
- Stub editing (read-only by spec).
- `DebugPageKind` / `DebugPageExposure` type re-exports (peer flagged these as stable; relevant when Findings page lands).
