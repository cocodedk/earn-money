import type { ApiError } from "./parseApiError";

export type ErrorSetters = {
  setFieldErrors: (errors: Record<string, string[]>) => void;
  setBannerError: (message: string) => void;
};

const KIND_MESSAGES: Record<"server" | "network", string> = {
  server: "Something went wrong. Please try again.",
  network: "Backend unreachable.",
};

// Maps a discriminated ApiError onto the form's field-error and
// banner-error setters. Both Create forms share this dispatch — the
// kind→effect mapping lives here so a new error kind is a one-file
// change.
export function applyParsedError(parsed: ApiError, set: ErrorSetters): void {
  if (parsed.kind === "field") {
    set.setFieldErrors(parsed.errors);
    return;
  }
  if (parsed.kind === "non_field") {
    set.setBannerError(parsed.errors[0]);
    return;
  }
  if (parsed.kind === "detail") {
    set.setBannerError(parsed.detail);
    return;
  }
  set.setBannerError(KIND_MESSAGES[parsed.kind]);
}
