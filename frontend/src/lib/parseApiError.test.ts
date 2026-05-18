import { describe, it, expect } from "vitest";
import { parseApiError } from "./parseApiError";

describe("parseApiError", () => {
  it("classifies field-keyed 400 as kind=field", async () => {
    const response = new Response(
      JSON.stringify({ name: ["already exists"] }),
      { status: 400, headers: { "content-type": "application/json" } },
    );
    expect(await parseApiError(response)).toEqual({
      kind: "field",
      errors: { name: ["already exists"] },
    });
  });

  it("classifies non_field_errors 400 as kind=non_field", async () => {
    const response = new Response(
      JSON.stringify({ non_field_errors: ["bad combo"] }),
      { status: 400, headers: { "content-type": "application/json" } },
    );
    expect(await parseApiError(response)).toEqual({
      kind: "non_field",
      errors: ["bad combo"],
    });
  });

  it("classifies non-validation 4xx as kind=detail", async () => {
    const response = new Response(JSON.stringify({ detail: "Not found." }), {
      status: 404,
      headers: { "content-type": "application/json" },
    });
    expect(await parseApiError(response)).toEqual({
      kind: "detail",
      detail: "Not found.",
      status: 404,
    });
  });

  it("falls back to 'Request failed' when detail is missing", async () => {
    const response = new Response("", { status: 403 });
    expect(await parseApiError(response)).toEqual({
      kind: "detail",
      detail: "Request failed",
      status: 403,
    });
  });

  it("classifies 5xx as kind=server", async () => {
    const response = new Response("Server boom", { status: 503 });
    expect(await parseApiError(response)).toEqual({
      kind: "server",
      status: 503,
    });
  });

  it("classifies thrown fetch errors as kind=network", async () => {
    expect(await parseApiError(new TypeError("Failed to fetch"))).toEqual({
      kind: "network",
    });
  });
});
