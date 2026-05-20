import styles from "./EmptyState.module.css";
import { Button } from "../Button";

export type EmptyStateProps = {
  message: string;
  action?: { label: string; onClick: () => void };
};

export function EmptyState({ message, action }: EmptyStateProps) {
  return (
    <div className={styles.empty} data-testid="empty-state">
      <p className={styles.message}>{message}</p>
      {action && (
        <Button onClick={action.onClick}>{action.label}</Button>
      )}
    </div>
  );
}
