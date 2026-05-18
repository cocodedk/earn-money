import { useEffect, useState } from "react";
import { useProjectsQuery } from "../features/projects/api";
import type { Project } from "../types/api";

const KEY = "em.frontend.currentProjectId";

export function useCurrentProject() {
  const [id, setIdState] = useState<string | null>(() =>
    window.localStorage.getItem(KEY),
  );

  function setId(next: string | null) {
    if (next === null) {
      window.localStorage.removeItem(KEY);
    } else {
      window.localStorage.setItem(KEY, next);
    }
    setIdState(next);
  }

  const query = useProjectsQuery();
  const project: Project | null =
    id && query.data
      ? (query.data.results.find((p) => p.id === id) ?? null)
      : null;

  useEffect(() => {
    if (id && query.data && !project) {
      setId(null);
    }
  }, [id, query.data, project]);

  return { id, setId, project };
}
