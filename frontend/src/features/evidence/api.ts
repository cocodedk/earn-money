import { useQuery } from "@tanstack/react-query";
import { http } from "../../lib/http";
import type { Evidence, Paginated, Uuid } from "../../types/api";

export const EVIDENCE_KEY = ["evidence"] as const;

export type EvidenceFilter = {
  project?: Uuid;
  target?: Uuid;
  scan_run?: Uuid;
  finding?: Uuid;
  source?: string;
};

function buildQuery(filter: EvidenceFilter): string {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(filter)) {
    if (v !== undefined && v !== "") params.set(k, v as string);
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function useEvidenceQuery(filter: EvidenceFilter = {}) {
  return useQuery({
    queryKey: [...EVIDENCE_KEY, filter] as const,
    queryFn: () =>
      http<Paginated<Evidence>>(`/api/evidence/${buildQuery(filter)}`),
  });
}

export function useEvidenceDetailQuery(id: Uuid | null) {
  return useQuery({
    queryKey: [...EVIDENCE_KEY, id] as const,
    queryFn: () => http<Evidence>(`/api/evidence/${id!}/`),
    enabled: Boolean(id),
  });
}
