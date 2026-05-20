import { http, HttpResponse } from "msw";
import { makeScanTargetRun } from "../features/scan-runs/__fixtures__/scan-target-run";

// Per-task handlers; tests append via server.use() for happy / error paths.
export const handlers = [
  http.get("/api/health/", () =>
    HttpResponse.json({ status: "ok", db: true }),
  ),
  http.get("/api/scan-runs/:id/target-runs/", () =>
    HttpResponse.json({
      count: 1,
      next: null,
      previous: null,
      results: [makeScanTargetRun()],
    }),
  ),
  http.get("/api/scan-runs/:id/events/", () =>
    HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
  ),
  http.get("/api/evidence/", () =>
    HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
  ),
  http.get("/api/findings/", () =>
    HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
  ),
];
