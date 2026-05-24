import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useScanRunEvents } from "../scan-runs/useScanRunEvents";
import type { Event as ApiEvent } from "../../types/api";
import type { AgentEventData, BudgetSnapshot } from "./types";
import { missionKey, missionTurnsKey, missionNotesKey } from "./api";

function isAgentEvent(event: ApiEvent, sessionId: string): boolean {
  if (!event.type.startsWith("agent.")) return false;
  const data = event.data as Partial<AgentEventData> | undefined;
  return data?.session_id === sessionId;
}

const SESSION_EVENTS = new Set([
  "agent.session_started",
  "agent.session_updated",
  "agent.phase_changed",
  "agent.budget_updated",
  "agent.mission_finished",
  "agent.session_failed",
  "agent.session_stopped",
]);
const TURNS_EVENTS = new Set([
  "agent.turn_started",
  "agent.action_proposed",
  "agent.action_executed",
  "agent.action_denied",
  "agent.turn_completed",
  "agent.turn_error",
  "agent.observation_created",
]);
const NOTES_EVENTS = new Set(["agent.note_created"]);

export type UseAgentEventsResult = {
  budgetOverlay: BudgetSnapshot | null;
  processedCount: number;
};

export function useAgentEvents(
  sessionId: string | undefined,
  scanRunId: string | undefined,
  isTerminal: boolean,
  sessionUpdatedAt?: string,
): UseAgentEventsResult {
  const client = useQueryClient();
  const processedRef = useRef(new Set<string>());
  const [budgetOverlay, setBudgetOverlay] = useState<BudgetSnapshot | null>(null);
  const [processedCount, setProcessedCount] = useState(0);

  const livePolling = Boolean(sessionId && scanRunId && !isTerminal);
  const { events } = useScanRunEvents(
    livePolling ? scanRunId : undefined,
    { livePolling },
  );

  useEffect(() => {
    processedRef.current = new Set<string>();
    setBudgetOverlay(null);
    setProcessedCount(0);
  }, [sessionId]);

  useEffect(() => {
    setBudgetOverlay(null);
  }, [sessionUpdatedAt, isTerminal]);

  const processEvents = useCallback(
    (allEvents: ApiEvent[]) => {
      if (!sessionId) return;
      let newCount = 0;
      let needSession = false;
      let needTurns = false;
      let needNotes = false;
      let latestSnapshot: BudgetSnapshot | undefined;

      for (const evt of allEvents) {
        if (processedRef.current.has(evt.id)) continue;
        if (!isAgentEvent(evt, sessionId)) continue;
        processedRef.current.add(evt.id);
        newCount++;
        if (SESSION_EVENTS.has(evt.type)) needSession = true;
        if (TURNS_EVENTS.has(evt.type)) needTurns = true;
        if (NOTES_EVENTS.has(evt.type)) needNotes = true;
        const data = evt.data as Partial<AgentEventData> | undefined;
        if (data?.budget_snapshot) latestSnapshot = data.budget_snapshot;
      }

      if (needSession) void client.invalidateQueries({ queryKey: missionKey(sessionId) });
      if (needTurns) void client.invalidateQueries({ queryKey: missionTurnsKey(sessionId) });
      if (needNotes) void client.invalidateQueries({ queryKey: missionNotesKey(sessionId) });
      if (latestSnapshot) setBudgetOverlay(latestSnapshot);
      if (newCount > 0) setProcessedCount((c) => c + newCount);
    },
    [sessionId, client],
  );

  useEffect(() => {
    processEvents(events);
  }, [events, processEvents]);

  return { budgetOverlay, processedCount };
}
