import styles from "./StatusBadge.module.css";
import type { ScanRunStatus, TargetStatus } from "../../types/api";

export type StatusBadgeStatus = ScanRunStatus | TargetStatus;

export type StatusBadgeFailure = { error: string; message: string };

export type StatusBadgeProps = {
  status: StatusBadgeStatus;
  failure?: StatusBadgeFailure;
};

const labelByStatus: Record<StatusBadgeStatus, string> = {
  queued: "Queued",
  running: "Running",
  paused: "Paused",
  stopping: "Stopping",
  stopped: "Stopped",
  failed: "Failed",
  done: "Done",
  active: "Active",
  retired: "Retired",
};

export function StatusBadge({ status, failure }: StatusBadgeProps) {
  const tooltip =
    status === "failed" && failure
      ? `${failure.error}: ${failure.message}`
      : undefined;
  return (
    <span
      className={`${styles.badge} ${styles[status]}`}
      data-testid="status-badge"
      data-status={status}
      title={tooltip}
    >
      {labelByStatus[status]}
    </span>
  );
}
