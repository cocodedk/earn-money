import { http, HttpResponse } from "msw";

// Per-task handlers; tests append via server.use() for happy / error paths.
export const handlers = [
  http.get("/api/health/", () =>
    HttpResponse.json({ status: "ok", db: true }),
  ),
];
