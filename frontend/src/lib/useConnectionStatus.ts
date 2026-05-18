import { useQuery } from "@tanstack/react-query";
import { http } from "./http";
import type { HealthResponse } from "../types/api";

export function useConnectionStatus() {
  const query = useQuery({
    queryKey: ["health"],
    queryFn: () => http<HealthResponse>("/api/health/"),
    refetchInterval: 30_000,
    staleTime: 0,
  });
  const connected = Boolean(
    query.data && query.data.status === "ok" && query.data.db,
  );
  return { connected, isLoading: query.isLoading };
}
