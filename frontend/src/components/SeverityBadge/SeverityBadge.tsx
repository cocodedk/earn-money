import styles from "./SeverityBadge.module.css";
import type { Severity } from "../../types/api";

export type SeverityBadgeProps = { severity: Severity };

const labelBySeverity: Record<Severity, string> = {
  info: "Info",
  low: "Low",
  medium: "Medium",
  high: "High",
  critical: "Critical",
};

export function SeverityBadge({ severity }: SeverityBadgeProps) {
  return (
    <span
      className={`${styles.badge} ${styles[severity]}`}
      data-testid="severity-badge"
      data-severity={severity}
    >
      {labelBySeverity[severity]}
    </span>
  );
}
