import { useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../../lib/http";
import type {
  CreateScanRunBody,
  Evidence,
  Finding,
  LifecycleAction,
  Paginated,
  ScanRun,
  ScanTargetRun,
  Uuid,
} from "../../types/api";

export function isRunActive(status: string | undefined): boolean {
  return status === "running" || status === "stopping";
}

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
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      return isRunActive(status) ? 2000 : false;
    },
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

type ScanRunChildOptions = { livePolling?: boolean };

function useScanRunChildQuery<T>(
  scanRunId: string | undefined,
  config: {
    endpoint: string;
    queryKey: readonly [...typeof SCAN_RUNS_KEY, string, string];
  },
  options?: ScanRunChildOptions,
) {
  const client = useQueryClient();
  const livePolling = Boolean(options?.livePolling);
  const prev = useRef(livePolling);
  const key = config.queryKey;

  useEffect(() => {
    if (prev.current && !livePolling && scanRunId) {
      void (async () => {
        await client.cancelQueries({ queryKey: key });
        await client.refetchQueries({ queryKey: key, type: "active" });
      })();
    }
    prev.current = livePolling;
  }, [livePolling, scanRunId, client, key]);

  return useQuery({
    queryKey: key,
    queryFn: () => http<Paginated<T>>(config.endpoint),
    enabled: Boolean(scanRunId),
    refetchInterval: livePolling ? 2000 : false,
  });
}

export const scanRunTargetRunsKey = (id: string) =>
  [...SCAN_RUNS_KEY, id, "target-runs"] as const;

export function useScanRunTargetRunsQuery(
  scanRunId: string | undefined,
  options?: ScanRunChildOptions,
) {
  return useScanRunChildQuery<ScanTargetRun>(
    scanRunId,
    {
      endpoint: `/api/scan-runs/${scanRunId}/target-runs/`,
      queryKey: scanRunTargetRunsKey(scanRunId ?? ""),
    },
    options,
  );
}

export const scanRunFindingsKey = (id: string) =>
  [...SCAN_RUNS_KEY, id, "findings"] as const;

export function useScanRunFindingsQuery(
  scanRunId: string | undefined,
  options?: ScanRunChildOptions,
) {
  return useScanRunChildQuery<Finding>(
    scanRunId,
    {
      endpoint: `/api/findings/?scan_run=${encodeURIComponent(scanRunId ?? "")}`,
      queryKey: scanRunFindingsKey(scanRunId ?? ""),
    },
    options,
  );
}

export const scanRunEvidenceKey = (id: string) =>
  [...SCAN_RUNS_KEY, id, "evidence"] as const;

export function useScanRunEvidenceQuery(
  scanRunId: string | undefined,
  options?: ScanRunChildOptions,
) {
  return useScanRunChildQuery<Evidence>(
    scanRunId,
    {
      endpoint: `/api/evidence/?scan_run=${encodeURIComponent(scanRunId ?? "")}`,
      queryKey: scanRunEvidenceKey(scanRunId ?? ""),
    },
    options,
  );
}
