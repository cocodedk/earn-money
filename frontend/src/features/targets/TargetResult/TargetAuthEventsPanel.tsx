import { useTargetAuthEventsQuery } from "../api.auth-events";
import { AuthEventPill } from "./AuthEventPill";
import styles from "./TargetAuthEventsPanel.module.css";

export function TargetAuthEventsPanel({ targetId }: { targetId: string }) {
  const query = useTargetAuthEventsQuery(targetId);
  const data = query.data;
  if (!data || data.count === 0) return null;
  const shown = data.results.length;
  const remaining = data.count - shown;
  return (
    <section
      className={styles.section}
      data-testid="target-auth-events-section"
    >
      <h3>Auth events for target ({data.count})</h3>
      <div className={styles.list}>
        {data.results.map((e) => (
          <AuthEventPill key={e.id} event={e} />
        ))}
      </div>
      {data.next !== null && remaining > 0 && (
        <p
          className={styles.footer}
          data-testid="target-auth-events-more"
        >
          +{remaining} more in the full events feed below.
        </p>
      )}
    </section>
  );
}
