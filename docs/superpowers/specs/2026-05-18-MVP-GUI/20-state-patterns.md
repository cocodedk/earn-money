# 20. State patterns

Every page that fetches or mutates data uses these four state branches. Codified so all pages behave identically and don't confuse the operator.

## Loading

| Surface | Pattern |
|---------|---------|
| Table | `<TableSkeleton rows={5} />` — same column widths as the real table, gray pulse rows. |
| Detail page | Render the page chrome (header + section headings) with `<Skeleton />` blocks where data goes; never block the whole page. |
| Button (mutation in flight) | Button enters `loading` state, label replaced by spinner, button width frozen, button disabled. |

## Empty

`<EmptyState message="…" />` with spec-mandated copy:

| Page | Message |
|------|---------|
| `/projects` (no rows) | `No projects yet.` |
| `/targets` | `No targets yet.` |
| `/scan-runs` | `No scan runs yet.` |
| `/findings` | `No findings yet.` |
| `/evidence` | `No evidence yet.` |

`/projects` empty state also renders a `Create project` action.

## Error (data fetch failed)

`<Callout variant="error" title="…">{detail}<button>Retry</button></Callout>` at the top of the page area. Underlying TanStack Query `useQuery` exposes a `refetch` function bound to the retry button.

## Error: connection unreachable

When `fetch` rejects with no response (DNS / CORS / network), every page shows `<Callout variant="error" title="Backend unreachable">…linking to /settings…</Callout>`. The top-bar `ConnectionPill` flips to red simultaneously.

## Validation (mutation 400)

The single source of truth is `lib/parseApiError.ts`:

```ts
type ApiError =
  | { kind: "field"; errors: Record<string, string[]> }   // 400 with field keys
  | { kind: "non_field"; errors: string[] }               // 400 with non_field_errors
  | { kind: "detail"; detail: string; status: number }    // 4xx with {detail}
  | { kind: "server"; status: number }                    // 5xx
  | { kind: "network" };                                  // fetch threw
```

### Field errors

`kind === "field"` → render the first message in `errors[fieldName]` under the matching `FormField` (`error={errors.name[0]}`). Input gets `aria-invalid="true"` + red border.

### Non-field errors

`kind === "non_field"` → render `<Callout variant="error">` above the form with the first message. Inputs stay neutral.

### Detail (non-validation 4xx)

`kind === "detail"` → red `Callout` at top of page with the `detail` string and a "back" link. Form (if any) stays editable.

### Server (5xx)

`kind === "server"` → red `Callout` "Something went wrong. Please try again." plus a retry button that re-fires the last mutation.

### Network

`kind === "network"` → red `Callout` "Backend unreachable" linking to `/settings`. Different copy from server error so the operator can distinguish.

## Success

| Surface | Pattern |
|---------|---------|
| Mutation → list | Invalidate the related `useQuery` cache key; list refetches; route back to list view. |
| Mutation → detail | Invalidate detail + list keys; stay on detail page; show no toast (per spec "no animations / no fancy" — success is silence + fresh data). |

## Race rules

- Stale cache while refetching: TanStack Query default `staleTime: 0` for slice 1; we keep showing the cached rows but mark them with no visible indicator (per "no fancy" — operator can reload manually).
- Concurrent mutation on the same scan run: the latest button click wins; previous in-flight requests are not cancelled but their responses are ignored if the cache has moved on.
