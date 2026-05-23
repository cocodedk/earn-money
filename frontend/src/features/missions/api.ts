import { useQuery } from "@tanstack/react-query";
import { http } from "../../lib/http";
import type { Paginated } from "../../types/api";
import type { AgentNote, AgentSession, AgentTurn } from "./types";
import { isTerminalStatus } from "./types";

export const MISSIONS_KEY = ["missions"] as const;

export const missionKey = (id: string) =>
  [...MISSIONS_KEY, id] as const;

export const missionTurnsKey = (id: string) =>
  [...MISSIONS_KEY, id, "turns"] as const;

export const missionNotesKey = (id: string) =>
  [...MISSIONS_KEY, id, "notes"] as const;

export function useSessionQuery(id: string | undefined) {
  return useQuery({
    queryKey: missionKey(id ?? ""),
    queryFn: () => http<AgentSession>(`/api/agent-sessions/${id}/`),
    enabled: Boolean(id),
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      return status && !isTerminalStatus(status) ? 2000 : false;
    },
  });
}

export function useTurnsQuery(sessionId: string | undefined) {
  return useQuery({
    queryKey: missionTurnsKey(sessionId ?? ""),
    queryFn: () =>
      http<Paginated<AgentTurn>>(
        `/api/agent-sessions/${sessionId}/turns/?page_size=200`,
      ),
    enabled: Boolean(sessionId),
  });
}

export function useNotesQuery(sessionId: string | undefined) {
  return useQuery({
    queryKey: missionNotesKey(sessionId ?? ""),
    queryFn: () =>
      http<Paginated<AgentNote>>(
        `/api/agent-sessions/${sessionId}/notes/?page_size=200`,
      ),
    enabled: Boolean(sessionId),
  });
}
