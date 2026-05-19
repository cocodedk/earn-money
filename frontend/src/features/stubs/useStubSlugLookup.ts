import { useMemo } from "react";
import { byKey } from "../../lib/byKey";
import { useStubsQuery } from "./api";

// Returns `(slug) => slug-or-raw-fallback` backed by the cached
// stubs query. Identity-ish today; here so list and detail pages
// pick up future enrichment (title, label, etc.) from one place.
export function useStubSlugLookup() {
  const stubs = useStubsQuery();
  return useMemo(
    () =>
      byKey(
        stubs.data,
        (s) => s.slug,
        (s) => s.slug,
        (slug) => slug,
      ),
    [stubs.data],
  );
}
