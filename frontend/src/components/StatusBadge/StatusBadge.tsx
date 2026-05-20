import styles from "./StatusBadge.module.css";

export type StatusBadgeProps<S extends string> = {
  status: S;
  palette: Record<S, string>;
};

export function StatusBadge<S extends string>({
  status,
  palette,
}: StatusBadgeProps<S>) {
  return (
    <span
      data-testid={`status-${status}`}
      className={`${styles.badge} ${palette[status]}`}
    >
      {status}
    </span>
  );
}
