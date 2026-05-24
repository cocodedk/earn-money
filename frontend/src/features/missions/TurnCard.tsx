import { useState } from "react";
import type { AgentTurn } from "./types";
import { describeTurn } from "./describeTurn";
import styles from "./TurnCard.module.css";

const GLYPHS: Record<string, string> = {
  success: "✓", denied: "⚠", error: "✗", running: "●", neutral: "•",
};
const LABELS: Record<string, string> = {
  success: "Completed", denied: "Blocked", error: "Failed",
  running: "Running", neutral: "Done",
};

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
  const tone = desc.tone;

  return (
    <div data-testid={`turn-card-${turn.index}`} className={styles.card}>
      <div className={styles.cardBody}>
        <span
          className={styles.icon}
          data-tone={tone}
          data-testid={`turn-icon-${tone}`}
          aria-label={LABELS[tone] ?? "Done"}
        >
          {GLYPHS[tone] ?? "•"}
        </span>
        <div className={styles.content}>
          <div className={styles.meta}>
            <span className={styles.turnNum}>#{turn.index}</span>
            <span className={styles.phaseBadge}>{turn.phase}</span>
            <span className={styles.time} title={turn.created_at}>
              {relativeTime(turn.created_at)}
            </span>
          </div>
          <p className={styles.title}>{desc.title}</p>
          {desc.result && <p className={styles.result}>{desc.result}</p>}
        </div>
      </div>
      {actions.length > 0 && (
        <button
          type="button"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          className={styles.detailsBtn}
        >
          Details
        </button>
      )}
      {open && actions.length > 0 && (
        <div className={styles.detailsPanel}>
          {actions.map((action) => (
            <div key={action.id} style={{ marginBottom: "0.5rem" }}>
              <div>Action: {action.action_type}</div>
              <div>Validation: {action.validation_status}</div>
              <div>Execution: {action.execution_status}</div>
              {action.denial_reason && <div>Denied: {action.denial_reason}</div>}
              {action.observations.length > 0 && (
                <details style={{ marginTop: "0.25rem" }}>
                  <summary>Observations ({action.observations.length})</summary>
                  <pre>
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
