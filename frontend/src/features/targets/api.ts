import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../../lib/http";
import type {
  CreateTargetBody,
  Evidence,
  Event,
  Finding,
  Paginated,
  ScanRun,
  Target,
} from "../../types/api";

export const TARGETS_KEY = ["targets"] as const;

export function useTargetsQuery() {
  return useQuery({
    queryKey: TARGETS_KEY,
    queryFn: () => http<Paginated<Target>>("/api/targets/"),
  });
}

export function useTargetQuery(id: string | undefined) {
  return useQuery({
    queryKey: [...TARGETS_KEY, id ?? ""] as const,
    queryFn: () => http<Target>(`/api/targets/${id}/`),
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
    },
  });
}

function useTargetChildQuery<T>(
  targetId: string | undefined,
  child: string,
) {
  const id = targetId ?? "";
  return useQuery({
    queryKey: [...TARGETS_KEY, id, child] as const,
    queryFn: () =>
      http<Paginated<T>>(`/api/${child}/?target=${encodeURIComponent(id)}`),
    enabled: Boolean(targetId),
  });
}

export function useTargetScanRunsQuery(targetId: string | undefined) {
  return useTargetChildQuery<ScanRun>(targetId, "scan-runs");
}

export function useTargetFindingsQuery(targetId: string | undefined) {
  return useTargetChildQuery<Finding>(targetId, "findings");
}

export function useTargetEvidenceQuery(targetId: string | undefined) {
  return useTargetChildQuery<Evidence>(targetId, "evidence");
}

export function useTargetEventsQuery(targetId: string | undefined) {
  return useTargetChildQuery<Event>(targetId, "events");
}
