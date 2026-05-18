import { ReactNode } from "react";
import styles from "./Callout.module.css";
import { Button } from "../Button";

export type CalloutProps = {
  variant: "info" | "warning" | "error";
  title?: ReactNode;
  children: ReactNode;
  action?: { label: string; onClick: () => void };
};

export function Callout({ variant, title, children, action }: CalloutProps) {
  return (
    <div
      role={variant === "error" ? "alert" : "status"}
      data-testid="callout"
      data-variant={variant}
      className={`${styles.callout} ${styles[variant]}`}
    >
      {title && <div className={styles.title}>{title}</div>}
      <div className={styles.body}>{children}</div>
      {action && (
        <div className={styles.action}>
          <Button variant="secondary" onClick={action.onClick}>
            {action.label}
          </Button>
        </div>
      )}
    </div>
  );
}
