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
];
