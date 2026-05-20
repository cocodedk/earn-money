import { useQuery } from "@tanstack/react-query";
import { http } from "./http";
import type { HealthResponse } from "../types/api";

export const HEALTH_KEY = ["health"] as const;

function useHealthQuery() {
  return useQuery({
    queryKey: HEALTH_KEY,
    queryFn: () => http<HealthResponse>("/api/health/"),
    refetchInterval: 30_000,
    staleTime: 30_000,
  });
}

export function useConnectionStatus() {
  const query = useHealthQuery();
  const connected = Boolean(
    query.data && query.data.status === "ok" && query.data.db,
  );
  return { connected, isLoading: query.isLoading };
}

export function useSystemHealth() {
  return useHealthQuery();
}
