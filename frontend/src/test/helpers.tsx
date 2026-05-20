import { useLocation } from "react-router-dom";
import { http as msw, HttpResponse } from "msw";
import { server } from "./server";

// Probe component that exposes the current router pathname under
// `data-testid="loc"` — used by tests that assert post-navigation routes.
export function LocationProbe() {
  return <span data-testid="loc">{useLocation().pathname}</span>;
}

// Install a GET handler for a paginated DRF endpoint serving `rows`.
// Mirrors DRF's PageNumberPagination response shape.
export function withPaginated(path: string, rows: unknown[]) {
  server.use(
    msw.get(path, () =>
      HttpResponse.json({
        count: rows.length,
        next: null,
        previous: null,
        results: rows,
      }),
    ),
  );
}

// Install a GET handler for an endpoint that returns a bare JSON array
// (used by /api/stubs/ — DRF pagination is intentionally disabled there).
export function withBareArray(path: string, rows: unknown[]) {
  server.use(msw.get(path, () => HttpResponse.json(rows)));
}
