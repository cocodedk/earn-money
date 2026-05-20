import styles from "./ConnectionPill.module.css";
import { useConnectionStatus } from "../../lib/useConnectionStatus";

export function ConnectionPill() {
  const { connected } = useConnectionStatus();
  return (
    <div
      className={styles.pill}
      data-testid="connection-pill"
      data-connected={connected ? "true" : "false"}
    >
      <span className={styles.dot} aria-hidden="true" />
      <span>{connected ? "Connected" : "Disconnected"}</span>
    </div>
  );
}
