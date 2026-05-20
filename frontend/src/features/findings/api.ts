import { useQuery } from "@tanstack/react-query";
import { http } from "../../lib/http";
import type {
  Confidence,
  Evidence,
  Finding,
  FindingStatus,
  Paginated,
  Severity,
  Uuid,
} from "../../types/api";

export type FindingsFilters = {
  project?: Uuid;
  target?: Uuid;
  scan_run?: Uuid;
  stub_slug?: string;
  severity?: Severity;
  confidence?: Confidence;
  status?: FindingStatus;
};

// Stable ordering so query keys + URLs are deterministic regardless of caller
// key order.
const FILTER_KEYS = [
  "project",
  "target",
  "scan_run",
  "stub_slug",
  "severity",
  "confidence",
  "status",
] as const satisfies readonly (keyof FindingsFilters)[];

function buildQueryString(filters: FindingsFilters): string {
  const params = new URLSearchParams();
  for (const key of FILTER_KEYS) {
    const value = filters[key];
    if (value !== undefined && value !== "") params.set(key, value);
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export const FINDINGS_KEY = ["findings"] as const;

export function findingsListKey(filters: FindingsFilters) {
  const flat: string[] = [];
  for (const key of FILTER_KEYS) {
    flat.push(key, filters[key] ?? "");
  }
  return [...FINDINGS_KEY, "list", ...flat] as const;
}

export function findingDetailKey(id: string) {
  return [...FINDINGS_KEY, "detail", id] as const;
}

export function useFindingsListQuery(filters: FindingsFilters) {
  return useQuery({
    queryKey: findingsListKey(filters),
    queryFn: () =>
      http<Paginated<Finding>>(`/api/findings/${buildQueryString(filters)}`),
  });
}

export function useFindingDetailQuery(findingId: string | undefined) {
  return useQuery({
    queryKey: findingDetailKey(findingId ?? ""),
    queryFn: () => http<Finding>(`/api/findings/${findingId}/`),
    enabled: Boolean(findingId),
  });
}

export function findingEvidenceKey(id: string) {
  return [...FINDINGS_KEY, "evidence", id] as const;
}

export function useFindingEvidenceQuery(findingId: string | undefined) {
  return useQuery({
    queryKey: findingEvidenceKey(findingId ?? ""),
    queryFn: () =>
      http<Paginated<Evidence>>(
        `/api/evidence/?finding=${encodeURIComponent(findingId as string)}`,
      ),
    enabled: Boolean(findingId),
  });
}
