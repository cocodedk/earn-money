import type { ConnectionStatus } from "./useScanRunEvents.utils";
import styles from "./EventsPanelHeader.module.css";

const KILL_SWITCH_TOOLTIP =
  "Live events disabled by kill switch — remove localStorage.disable_live_events and reload to re-enable.";

type Props = {
  status: ConnectionStatus;
  autoScroll: boolean;
  setAutoScroll: (next: (v: boolean) => boolean) => void;
  clear: () => void;
  reconnect: () => void;
};

export function EventsPanelHeader({
  status,
  autoScroll,
  setAutoScroll,
  clear,
  reconnect,
}: Props): JSX.Element {
  const reconnectDisabled = status === "closed" || status === "disabled";
  const reconnectTitle =
    status === "disabled" ? KILL_SWITCH_TOOLTIP : undefined;

  return (
    <header className="flex items-center gap-2">
      <h3>Live events</h3>
      <span
        data-testid="events-connection-status"
        data-status={status}
        className={styles.pill}
      >
        {status}
      </span>
      <button
        data-testid="events-autoscroll-toggle"
        type="button"
        onClick={() => setAutoScroll((v) => !v)}
      >
        Auto-scroll: {autoScroll ? "on" : "off"}
      </button>
      <button
        data-testid="events-clear-local"
        type="button"
        onClick={clear}
      >
        Clear
      </button>
      <button
        data-testid="events-reconnect"
        type="button"
        onClick={reconnect}
        disabled={reconnectDisabled}
        aria-disabled={reconnectDisabled ? "true" : undefined}
        title={reconnectTitle}
      >
        Reconnect
      </button>
    </header>
  );
}
