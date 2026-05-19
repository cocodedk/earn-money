import type { ApiError } from "./parseApiError";

export const BACKEND_UNREACHABLE = "Backend unreachable";

export type ErrorSetters = {
  setFieldErrors: (errors: Record<string, string[]>) => void;
  setBannerError: (message: string) => void;
};

export function applyParsedError(parsed: ApiError, set: ErrorSetters): void {
  switch (parsed.kind) {
    case "field":
      return set.setFieldErrors(parsed.errors);
    case "non_field":
      return set.setBannerError(parsed.errors[0]);
    case "detail":
      return set.setBannerError(parsed.detail);
    case "server":
      return set.setBannerError("Something went wrong. Please try again.");
    case "network":
      return set.setBannerError(`${BACKEND_UNREACHABLE}.`);
    /* v8 ignore next 4 — exhaustiveness guard; `never` makes a new ApiError.kind a type error */
    default: {
      const _exhaustive: never = parsed;
      return _exhaustive;
    }
  }
}
