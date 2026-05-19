import { useQuery } from "@tanstack/react-query";
import { http } from "../../lib/http";
import type { Stub, StubSummary } from "../../types/api";

export const STUBS_KEY = ["stubs"] as const;
export const stubKey = (slug: string) => [...STUBS_KEY, slug] as const;

export function useStubsQuery() {
  return useQuery({
    queryKey: STUBS_KEY,
    queryFn: () => http<StubSummary[]>("/api/stubs/"),
  });
}

export function useStubQuery(slug: string | undefined) {
  return useQuery({
    queryKey: stubKey(slug ?? ""),
    queryFn: () => http<Stub>(`/api/stubs/${slug}/`),
    enabled: Boolean(slug),
  });
}
