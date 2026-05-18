export type ApiError =
  | { kind: "field"; errors: Record<string, string[]> }
  | { kind: "non_field"; errors: string[] }
  | { kind: "detail"; detail: string; status: number }
  | { kind: "server"; status: number }
  | { kind: "network" };

export async function parseApiError(input: unknown): Promise<ApiError> {
  if (!(input instanceof Response)) {
    return { kind: "network" };
  }
  if (input.status >= 500) {
    return { kind: "server", status: input.status };
  }
  const body = (await input.json().catch(() => ({}))) as Record<string, unknown>;
  if (input.status === 400) {
    if (Array.isArray(body.non_field_errors)) {
      return { kind: "non_field", errors: body.non_field_errors as string[] };
    }
    return { kind: "field", errors: body as Record<string, string[]> };
  }
  const detail = typeof body.detail === "string" ? body.detail : "Request failed";
  return { kind: "detail", detail, status: input.status };
}
