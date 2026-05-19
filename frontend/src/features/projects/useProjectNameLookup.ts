import { useMemo } from "react";
import { byKey } from "../../lib/byKey";
import { useProjectsQuery } from "./api";

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
