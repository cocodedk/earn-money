import { useQuery } from "@tanstack/react-query";
import { http } from "../../lib/http";
import type { Stub, StubDetail } from "../../types/api";

export const STUBS_KEY = ["stubs"] as const;

export function useStubsQuery() {
  return useQuery({
    queryKey: STUBS_KEY,
    queryFn: () => http<Stub[]>("/api/stubs/"),
  });
}

export function useStubDetailQuery(slug: string | null) {
  return useQuery({
    queryKey: [...STUBS_KEY, slug] as const,
    queryFn: () => http<StubDetail>(`/api/stubs/${encodeURIComponent(slug!)}/`),
    enabled: Boolean(slug),
  });
}
