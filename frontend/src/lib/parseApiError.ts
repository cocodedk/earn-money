import { HttpError } from "./http";

export type ApiError =
  | { kind: "field"; errors: Record<string, string[]> }
  | { kind: "non_field"; errors: string[] }
  | { kind: "detail"; detail: string; status: number }
  | { kind: "server"; status: number }
  | { kind: "network" };

export async function parseApiError(input: unknown): Promise<ApiError> {
  // Accept either the raw Response or the HttpError wrapper so call
  // sites don't have to do `err instanceof HttpError ? err.response : err`.
  const response = input instanceof HttpError ? input.response : input;
  if (!(response instanceof Response)) {
    return { kind: "network" };
  }
  if (response.status >= 500) {
    return { kind: "server", status: response.status };
  }
  const body = (await response.json().catch(() => ({}))) as Record<string, unknown>;
  if (response.status === 400) {
    if (Array.isArray(body.non_field_errors)) {
      return { kind: "non_field", errors: body.non_field_errors as string[] };
    }
    // DRF APIException (e.g. InvalidTransition on a model action) returns
    // 400 with a single `{detail: "..."}` body — that's a top-level
    // explanation, not per-field validation. Classify as detail.
    if (typeof body.detail === "string") {
      return { kind: "detail", detail: body.detail, status: 400 };
    }
    return { kind: "field", errors: body as Record<string, string[]> };
  }
  const detail = typeof body.detail === "string" ? body.detail : "Request failed";
  return { kind: "detail", detail, status: response.status };
}
