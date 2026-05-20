import { useQuery } from "@tanstack/react-query";
import { http } from "../../lib/http";
import type { Evidence, Paginated, Uuid } from "../../types/api";

export type EvidenceFilters = {
  project?: Uuid;
  target?: Uuid;
  scan_run?: Uuid;
  finding?: Uuid;
  source?: string;
};

// Stable ordering so query keys + URLs are deterministic regardless of caller
// key order.
const FILTER_KEYS = [
  "project",
  "target",
  "scan_run",
  "finding",
  "source",
] as const satisfies readonly (keyof EvidenceFilters)[];

function buildQueryString(filters: EvidenceFilters): string {
  const params = new URLSearchParams();
  for (const key of FILTER_KEYS) {
    const value = filters[key];
    if (value !== undefined && value !== "") params.set(key, value);
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export const EVIDENCE_KEY = ["evidence"] as const;

export function evidenceListKey(filters: EvidenceFilters) {
  const flat: string[] = [];
  for (const key of FILTER_KEYS) {
    flat.push(key, filters[key] ?? "");
  }
  return [...EVIDENCE_KEY, "list", ...flat] as const;
}

export function evidenceDetailKey(id: string) {
  return [...EVIDENCE_KEY, "detail", id] as const;
}

export function useEvidenceListQuery(filters: EvidenceFilters) {
  return useQuery({
    queryKey: evidenceListKey(filters),
    queryFn: () =>
      http<Paginated<Evidence>>(`/api/evidence/${buildQueryString(filters)}`),
  });
}

export function useEvidenceDetailQuery(evidenceId: string | undefined) {
  return useQuery({
    queryKey: evidenceDetailKey(evidenceId ?? ""),
    queryFn: () => http<Evidence>(`/api/evidence/${evidenceId}/`),
    enabled: Boolean(evidenceId),
  });
}
