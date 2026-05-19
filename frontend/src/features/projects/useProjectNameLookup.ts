import { useMemo } from "react";
import { byKey } from "../../lib/byKey";
import { useProjectsQuery } from "./api";

// Returns `(projectId) => projectName-or-short-uuid` backed by the
// cached projects query. Memoised on the cached results so the lookup
// closure stays stable across unrelated re-renders.
export function useProjectNameLookup() {
  const projects = useProjectsQuery();
  return useMemo(
    () =>
      byKey(
        projects.data?.results,
        (p) => p.id,
        (p) => p.name,
        (id) => id.slice(0, 8),
      ),
    [projects.data?.results],
  );
}
