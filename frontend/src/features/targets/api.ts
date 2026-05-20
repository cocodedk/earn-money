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
export const targetKey = (id: string) => [...TARGETS_KEY, id] as const;

export function useTargetsQuery() {
  return useQuery({
    queryKey: TARGETS_KEY,
    queryFn: () => http<Paginated<Target>>("/api/targets/"),
  });
}

export function useTargetQuery(id: string | undefined) {
  return useQuery({
    queryKey: targetKey(id ?? ""),
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
  config: {
    endpoint: string;
    queryKey: readonly [...typeof TARGETS_KEY, string, string];
  },
) {
  return useQuery({
    queryKey: config.queryKey,
    queryFn: () => http<Paginated<T>>(config.endpoint),
    enabled: Boolean(targetId),
  });
}

const childKey = (id: string, child: string) =>
  [...TARGETS_KEY, id, child] as const;

export function useTargetScanRunsQuery(targetId: string | undefined) {
  return useTargetChildQuery<ScanRun>(targetId, {
    endpoint: `/api/scan-runs/?target=${encodeURIComponent(targetId ?? "")}`,
    queryKey: childKey(targetId ?? "", "scan-runs"),
  });
}

export function useTargetFindingsQuery(targetId: string | undefined) {
  return useTargetChildQuery<Finding>(targetId, {
    endpoint: `/api/findings/?target=${encodeURIComponent(targetId ?? "")}`,
    queryKey: childKey(targetId ?? "", "findings"),
  });
}

export function useTargetEvidenceQuery(targetId: string | undefined) {
  return useTargetChildQuery<Evidence>(targetId, {
    endpoint: `/api/evidence/?target=${encodeURIComponent(targetId ?? "")}`,
    queryKey: childKey(targetId ?? "", "evidence"),
  });
}

export function useTargetEventsQuery(targetId: string | undefined) {
  return useTargetChildQuery<Event>(targetId, {
    endpoint: `/api/events/?target=${encodeURIComponent(targetId ?? "")}`,
    queryKey: childKey(targetId ?? "", "events"),
  });
}
