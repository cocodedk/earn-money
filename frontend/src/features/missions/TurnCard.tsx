import { useState } from "react";
import type { AgentTurn } from "./types";
import { describeTurn } from "./describeTurn";

const TONE_ICON: Record<string, { testId: string; label: string; cls: string }> = {
  success: { testId: "turn-icon-success", label: "Completed", cls: "text-green-600" },
  denied:  { testId: "turn-icon-denied",  label: "Blocked",   cls: "text-yellow-600" },
  error:   { testId: "turn-icon-error",   label: "Failed",    cls: "text-red-600" },
  running: { testId: "turn-icon-running", label: "Running",   cls: "text-blue-500" },
  neutral: { testId: "turn-icon-neutral", label: "Done",      cls: "text-gray-500" },
};

function StatusIcon({ tone }: { tone: string }) {
  const cfg = TONE_ICON[tone] ?? TONE_ICON.neutral;
  return (
    <span data-testid={cfg.testId} aria-label={cfg.label} className={cfg.cls}>
      {tone === "success" && "✓"}
      {tone === "denied" && "⚠"}
      {tone === "error" && "✗"}
      {tone === "running" && "●"}
      {tone === "neutral" && "•"}
    </span>
  );
}

function relativeTime(iso: string): string {
  const diff = Math.max(0, Date.now() - new Date(iso).getTime());
  const secs = Math.floor(diff / 1000);
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  return `${Math.floor(mins / 60)}h ago`;
}

export function TurnCard({ turn }: { turn: AgentTurn }) {
  const [open, setOpen] = useState(false);
  const desc = describeTurn(turn);
  const actions = turn.actions;

  return (
    <div data-testid={`turn-card-${turn.index}`} className="py-2 border-b">
      <div className="flex items-start gap-2">
        <StatusIcon tone={desc.tone} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-sm text-gray-500">#{turn.index}</span>
            <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100">{turn.phase}</span>
            <span className="text-xs text-gray-400" title={turn.created_at}>
              {relativeTime(turn.created_at)}
            </span>
          </div>
          <p className="mt-0.5">{desc.title}</p>
          {desc.result && <p className="text-sm text-gray-600 mt-0.5">{desc.result}</p>}
        </div>
      </div>
      {actions.length > 0 && (
        <button
          type="button"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          className="text-xs text-gray-500 mt-1 underline"
        >
          Details
        </button>
      )}
      {open && actions.length > 0 && (
        <div className="mt-1 text-xs text-gray-500 bg-gray-50 p-2 rounded font-mono">
          {actions.map((action) => (
            <div key={action.id} className="mb-2 last:mb-0">
              <div>Action: {action.action_type}</div>
              <div>Validation: {action.validation_status}</div>
              <div>Execution: {action.execution_status}</div>
              {action.denial_reason && <div>Denied: {action.denial_reason}</div>}
              {action.observations.length > 0 && (
                <details className="mt-1">
                  <summary>Observations ({action.observations.length})</summary>
                  <pre className="max-h-48 overflow-auto whitespace-pre-wrap">
                    {JSON.stringify(action.observations.map((o) => ({
                      type: o.observation_type, data: o.data,
                    })), null, 2)}
                  </pre>
                </details>
              )}
            </div>
          ))}
          <div>Tokens: {turn.input_tokens} in / {turn.output_tokens} out</div>
          <div>Time: {turn.created_at}</div>
        </div>
      )}
    </div>
  );
}
