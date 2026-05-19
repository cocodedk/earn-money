import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../../lib/http";
import { PROJECTS_KEY } from "../projects/api";
import type {
  CreateTargetBody,
  Paginated,
  Target,
  Uuid,
} from "../../types/api";

export const TARGETS_KEY = ["targets"] as const;

export function useTargetsQuery(projectId: Uuid | null) {
  const url = projectId
    ? `/api/targets/?project=${encodeURIComponent(projectId)}`
    : "/api/targets/";
  return useQuery({
    queryKey: [...TARGETS_KEY, { project: projectId }] as const,
    queryFn: () => http<Paginated<Target>>(url),
  });
}

export function useTargetDetailQuery(id: Uuid | null) {
  return useQuery({
    queryKey: [...TARGETS_KEY, id] as const,
    queryFn: () => http<Target>(`/api/targets/${id!}/`),
    enabled: Boolean(id),
  });
}

export function useCreateTargetMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateTargetBody) =>
      http<Target>("/api/targets/", { method: "POST", body }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: TARGETS_KEY });
      void client.invalidateQueries({ queryKey: PROJECTS_KEY });
    },
  });
}
