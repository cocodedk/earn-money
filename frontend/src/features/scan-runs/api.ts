import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../../lib/http";
import { PROJECTS_KEY } from "../projects/api";
import type {
  CreateScanRunBody,
  Evidence,
  Finding,
  LifecycleAction,
  Paginated,
  ScanRun,
  ScanRunStatus,
  TargetRun,
  Uuid,
} from "../../types/api";

export const SCAN_RUNS_KEY = ["scan-runs"] as const;

type ScanRunsFilter = {
  project?: Uuid;
  status?: ScanRunStatus;
  stub_slug?: string;
};

export function useScanRunsQuery(filter: ScanRunsFilter = {}) {
  const search = new URLSearchParams();
  if (filter.project) search.set("project", filter.project);
  if (filter.status) search.set("status", filter.status);
  if (filter.stub_slug) search.set("stub_slug", filter.stub_slug);
  const qs = search.toString();
  const url = qs ? `/api/scan-runs/?${qs}` : "/api/scan-runs/";
  return useQuery({
    queryKey: [...SCAN_RUNS_KEY, filter] as const,
    queryFn: () => http<Paginated<ScanRun>>(url),
  });
}

export function useScanRunDetailQuery(id: Uuid | null) {
  return useQuery({
    queryKey: [...SCAN_RUNS_KEY, id] as const,
    queryFn: () => http<ScanRun>(`/api/scan-runs/${id!}/`),
    enabled: Boolean(id),
  });
}

export function useCreateScanRunMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateScanRunBody) =>
      http<ScanRun>("/api/scan-runs/", { method: "POST", body }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: SCAN_RUNS_KEY });
      void client.invalidateQueries({ queryKey: PROJECTS_KEY });
    },
  });
}

export function useScanRunLifecycleMutation(id: Uuid) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (action: LifecycleAction) =>
      http<void>(`/api/scan-runs/${id}/${action}/`, { method: "POST" }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: [...SCAN_RUNS_KEY, id] });
      void client.invalidateQueries({ queryKey: SCAN_RUNS_KEY });
    },
  });
}

export function useScanRunFindingsQuery(id: Uuid | null) {
  return useQuery({
    queryKey: [...SCAN_RUNS_KEY, id, "findings"] as const,
    queryFn: () => http<Paginated<Finding>>(`/api/scan-runs/${id!}/findings/`),
    enabled: Boolean(id),
  });
}

export function useScanRunEvidenceQuery(id: Uuid | null) {
  return useQuery({
    queryKey: [...SCAN_RUNS_KEY, id, "evidence"] as const,
    queryFn: () => http<Paginated<Evidence>>(`/api/scan-runs/${id!}/evidence/`),
    enabled: Boolean(id),
  });
}

export function useScanRunTargetRunsQuery(id: Uuid | null) {
  return useQuery({
    queryKey: [...SCAN_RUNS_KEY, id, "target-runs"] as const,
    queryFn: () =>
      http<Paginated<TargetRun>>(`/api/scan-runs/${id!}/target-runs/`),
    enabled: Boolean(id),
  });
}
