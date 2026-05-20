import { Routes, Route } from "react-router-dom";
import { renderWithProviders } from "../../../../test/renderWithProviders";
import { withPaginated } from "../../../../test/helpers";
import { TargetResult } from "../../TargetResult";

export const TARGET_ID = "22222222-2222-2222-2222-222222222222";

export const TARGET = {
  id: TARGET_ID,
  project: "p-1",
  base_url: "https://dvwa.cocode.dk",
  host: "dvwa.cocode.dk",
  ip: "1.2.3.4",
  status: "active" as const,
  created_at: "2026-05-19T08:00:00.000000Z",
  updated_at: "2026-05-19T08:00:00.000000Z",
};

export const PROJECT = {
  id: "p-1",
  name: "Local Lab",
  description: "",
  target_count: 1,
  scan_run_count: 1,
  created_at: "2026-05-19T08:00:00.000000Z",
};

export function mountTargetResult() {
  withPaginated("/api/projects/", [PROJECT]);
  return renderWithProviders(
    <Routes>
      <Route path="/targets/:targetId/results" element={<TargetResult />} />
    </Routes>,
    { route: `/targets/${TARGET_ID}/results` },
  );
}

export function paginatedJson<T>(rows: T[], next: string | null = null) {
  return { count: rows.length, next, previous: null, results: rows };
}

export function emptyPage() {
  return { count: 0, next: null, previous: null, results: [] };
}
