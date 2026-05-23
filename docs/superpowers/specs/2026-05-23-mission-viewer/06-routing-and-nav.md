# Mission Viewer — Routing and Navigation

## Route

Add to `app/routes.ts`:

```typescript
missionDetail: "/missions/:sessionId",
```

Helper:

```typescript
export const missionDetailPath = (sessionId: string) =>
  `/missions/${sessionId}`;
```

## App.tsx

Add one `<Route>` inside `<Layout>`:

```tsx
<Route path={ROUTES.missionDetail} element={<MissionViewerPage />} />
```

## Navigation

No nav entry or sidebar link in this slice.  The page is reached by
navigating after a successful `POST /api/agent-sessions/` from the
Start Mission flow (future slice on targets or scan-runs page).

Direct URL access works: `/missions/<uuid>` loads the session.

## Future

A missions list page (`/missions`) and nav entry can be added when
multiple missions exist.  Out of scope for this slice.

## Tests

- `app/routes.test.ts` covers `ROUTES.missionDetail` and
  `missionDetailPath(sessionId)`.
- `App.e2e.*` or `MissionViewerPage.test.tsx` verifies direct navigation
  to `/missions/<uuid>` renders the mission viewer route.
- No nav test should expect a Missions item in this slice.
