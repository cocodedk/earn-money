import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../../lib/http";
import type {
  CreateScanRunBody,
  LifecycleAction,
  Paginated,
  ScanRun,
  Uuid,
} from "../../types/api";

export const SCAN_RUNS_KEY = ["scan-runs"] as const;
export const scanRunKey = (id: string) => [...SCAN_RUNS_KEY, id] as const;

export function useScanRunsQuery() {
  return useQuery({
    queryKey: SCAN_RUNS_KEY,
    queryFn: () => http<Paginated<ScanRun>>("/api/scan-runs/"),
  });
}

export function useScanRunQuery(id: string | undefined) {
  return useQuery({
    queryKey: scanRunKey(id ?? ""),
    queryFn: () => http<ScanRun>(`/api/scan-runs/${id}/`),
    enabled: Boolean(id),
  });
}

export function useCreateScanRunMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateScanRunBody) =>
      http<ScanRun>("/api/scan-runs/", { method: "POST", body }),
    onSuccess: () =>
      void client.invalidateQueries({ queryKey: SCAN_RUNS_KEY }),
  });
}

function makeLifecycleHook(action: LifecycleAction) {
  return function useLifecycleMutation() {
    const client = useQueryClient();
    return useMutation({
      mutationFn: (id: Uuid) =>
        http<ScanRun>(`/api/scan-runs/${id}/${action}/`, { method: "POST" }),
      onSuccess: () =>
        void client.invalidateQueries({ queryKey: SCAN_RUNS_KEY }),
    });
  };
}

export const useStartScanRunMutation = makeLifecycleHook("start");
export const usePauseScanRunMutation = makeLifecycleHook("pause");
export const useResumeScanRunMutation = makeLifecycleHook("resume");
export const useStopScanRunMutation = makeLifecycleHook("stop");
