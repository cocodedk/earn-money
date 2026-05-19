import { useMemo } from "react";
import { byKey } from "../../lib/byKey";
import { useStubsQuery } from "./api";

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
