import type { AgentSession, BudgetSnapshot } from "./types";
import { isTerminalStatus } from "./types";

type Props = {
  session: AgentSession;
  budgetOverlay: BudgetSnapshot | null;
};

function usedTurns(budget: BudgetSnapshot): number {
  return budget.mission?.turns ?? budget.turns ?? 0;
}

function budgetText(session: AgentSession, overlay: BudgetSnapshot | null): string {
  const snap = overlay ?? session.consumed_budget;
  const used = usedTurns(snap);
  const max = session.mission_budget.max_turns;
  return max != null ? `${used} of ${max} turns used` : `${used} turns used`;
}

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-gray-200 text-gray-700",
  running: "bg-blue-100 text-blue-700",
  paused: "bg-yellow-100 text-yellow-700",
  completed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  stopped: "bg-gray-200 text-gray-700",
};

export function MissionStrip({ session, budgetOverlay }: Props) {
  const isTerminal = isTerminalStatus(session.status);
  return (
    <div className="sticky top-0 z-10 bg-white border-b px-4 py-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <div className="flex items-center gap-2 min-w-0">
          <span className="font-semibold truncate">{session.mission_profile}</span>
          <span className="text-sm text-gray-500 truncate">{session.target_host}</span>
          <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[session.status] ?? ""}`}>
            {session.status}
          </span>
        </div>
        <div className="flex items-center gap-1" role="list" aria-label="Mission phases">
          {session.active_phases.map((phase, i) => (
            <span key={phase} role="listitem">
              {i > 0 && <span className="text-gray-300 mr-1" aria-hidden="true">{"→"}</span>}
              <span
                data-testid={`phase-chip-${phase}`}
                data-current={phase === session.current_phase ? "true" : "false"}
                aria-current={phase === session.current_phase ? "step" : undefined}
                className={`text-xs px-1.5 py-0.5 rounded ${
                  phase === session.current_phase
                    ? "bg-blue-600 text-white font-medium"
                    : "bg-gray-100 text-gray-600"
                }`}
              >
                {phase}
              </span>
            </span>
          ))}
        </div>
        <span className="text-sm text-gray-600 ml-auto">
          {budgetText(session, budgetOverlay)}
        </span>
      </div>
      {isTerminal && (
        <p className="text-sm text-gray-600 mt-1">
          {session.terminal_reason || "Mission ended."}
        </p>
      )}
    </div>
  );
}
