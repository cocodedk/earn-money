import { describe, it, expect } from "vitest";
import { ROUTES, scanRunDetailPath, stubDetailPath } from "./routes";

describe("routes registry", () => {
  it("locks the navigation route paths", () => {
    expect(ROUTES.stubs).toBe("/stubs");
    expect(ROUTES.stubDetail).toBe("/stubs/:slug");
    expect(ROUTES.scanRuns).toBe("/scan-runs");
    expect(ROUTES.scanRunsNew).toBe("/scan-runs/new");
    expect(ROUTES.scanRunDetail).toBe("/scan-runs/:id");
  });

  it("builds a stub detail path from a composite slug", () => {
    expect(stubDetailPath("1.1")).toBe("/stubs/1.1");
    expect(stubDetailPath("24.9")).toBe("/stubs/24.9");
  });

  it("builds a scan run detail path from a UUID", () => {
    expect(scanRunDetailPath("r-1")).toBe("/scan-runs/r-1");
    expect(scanRunDetailPath("abc-123")).toBe("/scan-runs/abc-123");
  });
});
