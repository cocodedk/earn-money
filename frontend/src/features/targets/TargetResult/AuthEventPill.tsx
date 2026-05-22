import { useId, useState } from "react";
import type { Event } from "../../../types/api";
import styles from "./AuthEventPill.module.css";

const LABELS: Record<string, string> = {
  "auth.probe_refused": "Probe refused",
  "auth.fixture_required": "Fixture required",
  "auth.finding_candidate": "Finding candidate",
};

const VARIANTS: Record<string, "warning" | "info" | "alert"> = {
  "auth.probe_refused": "warning",
  "auth.fixture_required": "info",
  "auth.finding_candidate": "alert",
};

function fmtTime(ts: string): string {
  return new Date(ts).toLocaleTimeString();
}

export function AuthEventPill({ event }: { event: Event }) {
  const detailId = useId();
  const [expanded, setExpanded] = useState(false);
  const variant = VARIANTS[event.type] ?? "info";
  const label = LABELS[event.type] ?? event.type;
  /* c8 ignore next 1 -- defensive fallback; Event.data is non-nullable per type but guards against runtime mutations */
  const payload = event.data ?? {};
  return (
    <div className={styles.row} data-variant={variant}>
      <button
        type="button"
        className={styles.pill}
        aria-expanded={expanded}
        aria-controls={detailId}
        onClick={() => setExpanded((v) => !v)}
      >
        <span className={styles.label}>{label}</span>
        <span className={styles.time} data-testid="auth-event-pill-time">
          {fmtTime(event.created_at)}
        </span>
      </button>
      {expanded && (
        <div id={detailId} className={styles.detail} data-testid="auth-event-pill-detail">
          <p>{event.message}</p>
          <pre>{JSON.stringify(payload, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
