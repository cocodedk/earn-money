import { useQuery } from "@tanstack/react-query";
import { http } from "../../lib/http";
import type { Event, Paginated } from "../../types/api";
import { TARGETS_KEY } from "./api";

export const AUTH_EVENT_TYPES = [
  "auth.probe_refused",
  "auth.fixture_required",
  "auth.finding_candidate",
] as const;

export function useTargetAuthEventsQuery(targetId: string | undefined) {
  const id = targetId ?? "";
  return useQuery({
    queryKey: [...TARGETS_KEY, id, "auth-events"] as const,
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("target", id);
      for (const t of AUTH_EVENT_TYPES) params.append("type", t);
      const page = await http<Paginated<Event>>(
        `/api/events/?${params.toString()}`,
      );
      return { ...page, results: [...page.results].reverse() };
    },
    enabled: Boolean(targetId),
  });
}
