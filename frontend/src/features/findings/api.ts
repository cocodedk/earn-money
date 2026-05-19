import { useQuery } from "@tanstack/react-query";
import { http } from "../../lib/http";
import type {
  Confidence,
  Finding,
  FindingStatus,
  Paginated,
  Severity,
  Uuid,
} from "../../types/api";

export const FINDINGS_KEY = ["findings"] as const;

export type FindingsFilter = {
  project?: Uuid;
  target?: Uuid;
  scan_run?: Uuid;
  stub?: string;
  severity?: Severity;
  confidence?: Confidence;
  status?: FindingStatus;
};

function buildQuery(filter: FindingsFilter): string {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(filter)) {
    if (v !== undefined && v !== "") params.set(k, v as string);
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function useFindingsQuery(filter: FindingsFilter = {}) {
  return useQuery({
    queryKey: [...FINDINGS_KEY, filter] as const,
    queryFn: () =>
      http<Paginated<Finding>>(`/api/findings/${buildQuery(filter)}`),
  });
}

export function useFindingDetailQuery(id: Uuid | null) {
  return useQuery({
    queryKey: [...FINDINGS_KEY, id] as const,
    queryFn: () => http<Finding>(`/api/findings/${id!}/`),
    enabled: Boolean(id),
  });
}
