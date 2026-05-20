import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../../lib/http";
import type { CreateProjectBody, Paginated, Project } from "../../types/api";

export const PROJECTS_KEY = ["projects"] as const;

export function useProjectsQuery() {
  return useQuery({
    queryKey: PROJECTS_KEY,
    queryFn: () => http<Paginated<Project>>("/api/projects/"),
  });
}

export function useCreateProjectMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateProjectBody) =>
      http<Project>("/api/projects/", { method: "POST", body }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: PROJECTS_KEY });
    },
  });
}
