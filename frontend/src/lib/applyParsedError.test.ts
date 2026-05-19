import { describe, it, expect, vi } from "vitest";
import { applyParsedError } from "./applyParsedError";

function makeSetters() {
  return {
    setFieldErrors: vi.fn(),
    setBannerError: vi.fn(),
  };
}

describe("applyParsedError", () => {
  it("routes field errors to setFieldErrors", () => {
    const set = makeSetters();
    applyParsedError(
      { kind: "field", errors: { name: ["already exists"] } },
      set,
    );
    expect(set.setFieldErrors).toHaveBeenCalledWith({ name: ["already exists"] });
    expect(set.setBannerError).not.toHaveBeenCalled();
  });

  it("routes the first non_field error to the banner", () => {
    const set = makeSetters();
    applyParsedError({ kind: "non_field", errors: ["bad combo"] }, set);
    expect(set.setBannerError).toHaveBeenCalledWith("bad combo");
    expect(set.setFieldErrors).not.toHaveBeenCalled();
  });

  it("routes a detail message to the banner", () => {
    const set = makeSetters();
    applyParsedError({ kind: "detail", detail: "Forbidden.", status: 403 }, set);
    expect(set.setBannerError).toHaveBeenCalledWith("Forbidden.");
  });

  it("renders a generic banner on server errors", () => {
    const set = makeSetters();
    applyParsedError({ kind: "server", status: 503 }, set);
    expect(set.setBannerError).toHaveBeenCalledWith(
      "Something went wrong. Please try again.",
    );
  });

  it("renders Backend unreachable on network errors", () => {
    const set = makeSetters();
    applyParsedError({ kind: "network" }, set);
    expect(set.setBannerError).toHaveBeenCalledWith("Backend unreachable.");
  });
});
