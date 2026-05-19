import { describe, it, expect } from "vitest";
import { ROUTES, stubDetailPath } from "./routes";

describe("routes registry", () => {
  it("locks the navigation route paths", () => {
    expect(ROUTES.stubs).toBe("/stubs");
    expect(ROUTES.stubDetail).toBe("/stubs/:slug");
  });

  it("builds a stub detail path from a composite slug", () => {
    expect(stubDetailPath("1.1")).toBe("/stubs/1.1");
    expect(stubDetailPath("24.9")).toBe("/stubs/24.9");
  });
});
