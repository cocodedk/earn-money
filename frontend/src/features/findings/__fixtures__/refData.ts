import { http as msw, HttpResponse } from "msw";
import { server } from "../../../test/server";
import { makeScanRun } from "../../scan-runs/__fixtures__/scan-run";

export const PROJECT = {
  id: "p-1",
  name: "Local Lab",
  description: "",
  target_count: 1,
  scan_run_count: 1,
  created_at: "2026-05-19T08:00:00.000000Z",
};

export const TARGET = {
  id: "t-1",
  project: "p-1",
  base_url: "https://dvwa.cocode.dk",
  host: "dvwa.cocode.dk",
  ip: null,
  status: "active" as const,
  created_at: "2026-05-19T08:00:00Z",
  updated_at: "2026-05-19T08:00:00Z",
};

export const STUB = {
  slug: "1.1-headers",
  phase: 1,
  spec: 1,
  phase_slug: "p1",
  spec_slug: "headers",
  title: "Headers",
  phase_title: "Phase 1",
  category: "headers",
  status: "done" as const,
  fixture: "dvwa",
  path: "x",
};

export function paged<T>(rows: T[], next: string | null = null) {
  return { count: rows.length, next, previous: null, results: rows };
}

export function setupFiltersRefData() {
  server.use(
    msw.get("/api/projects/", () => HttpResponse.json(paged([PROJECT]))),
    msw.get("/api/targets/", () => HttpResponse.json(paged([TARGET]))),
    msw.get("/api/scan-runs/", () =>
      HttpResponse.json(paged([makeScanRun({ id: "sr-1" })])),
    ),
    msw.get("/api/stubs/", () => HttpResponse.json([STUB])),
  );
}
