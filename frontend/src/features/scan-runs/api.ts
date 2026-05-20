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

export const scanRunTargetRunsKey = (id: string) =>
  [...SCAN_RUNS_KEY, id, "target-runs"] as const;

type ScanRunChildOptions = { livePolling?: boolean };

export function useScanRunTargetRunsQuery(
  scanRunId: string | undefined,
  options?: ScanRunChildOptions,
) {
  const client = useQueryClient();
  const livePolling = Boolean(options?.livePolling);
  const prev = useRef(livePolling);

  useEffect(() => {
    if (prev.current && !livePolling && scanRunId) {
      const key = scanRunTargetRunsKey(scanRunId);
      void (async () => {
        await client.cancelQueries({ queryKey: key });
        await client.refetchQueries({ queryKey: key, type: "active" });
      })();
    }
    prev.current = livePolling;
  }, [livePolling, scanRunId, client]);

  return useQuery({
    queryKey: scanRunTargetRunsKey(scanRunId ?? ""),
    queryFn: () =>
      http<Paginated<ScanTargetRun>>(`/api/scan-runs/${scanRunId}/target-runs/`),
    enabled: Boolean(scanRunId),
    refetchInterval: livePolling ? 2000 : false,
  });
}

export const scanRunFindingsKey = (id: string) =>
  [...SCAN_RUNS_KEY, id, "findings"] as const;

export function useScanRunFindingsQuery(
  scanRunId: string | undefined,
  options?: ScanRunChildOptions,
) {
  const client = useQueryClient();
  const livePolling = Boolean(options?.livePolling);
  const prev = useRef(livePolling);

  useEffect(() => {
    if (prev.current && !livePolling && scanRunId) {
      const key = scanRunFindingsKey(scanRunId);
      void (async () => {
        await client.cancelQueries({ queryKey: key });
        await client.refetchQueries({ queryKey: key, type: "active" });
      })();
    }
    prev.current = livePolling;
  }, [livePolling, scanRunId, client]);

  return useQuery({
    queryKey: scanRunFindingsKey(scanRunId ?? ""),
    queryFn: () =>
      http<Paginated<Finding>>(
        `/api/findings/?scan_run=${encodeURIComponent(scanRunId ?? "")}`,
      ),
    enabled: Boolean(scanRunId),
    refetchInterval: livePolling ? 2000 : false,
  });
}

export const scanRunEvidenceKey = (id: string) =>
  [...SCAN_RUNS_KEY, id, "evidence"] as const;

export function useScanRunEvidenceQuery(
  scanRunId: string | undefined,
  options?: ScanRunChildOptions,
) {
  const client = useQueryClient();
  const livePolling = Boolean(options?.livePolling);
  const prev = useRef(livePolling);

  useEffect(() => {
    if (prev.current && !livePolling && scanRunId) {
      const key = scanRunEvidenceKey(scanRunId);
      void (async () => {
        await client.cancelQueries({ queryKey: key });
        await client.refetchQueries({ queryKey: key, type: "active" });
      })();
    }
    prev.current = livePolling;
  }, [livePolling, scanRunId, client]);

  return useQuery({
    queryKey: scanRunEvidenceKey(scanRunId ?? ""),
    queryFn: () =>
      http<Paginated<Evidence>>(
        `/api/evidence/?scan_run=${encodeURIComponent(scanRunId ?? "")}`,
      ),
    enabled: Boolean(scanRunId),
    refetchInterval: livePolling ? 2000 : false,
  });
}
