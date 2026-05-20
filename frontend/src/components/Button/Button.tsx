import { ReactNode } from "react";
import styles from "./Button.module.css";

export type ButtonProps = {
  variant?: "primary" | "secondary" | "danger";
  loading?: boolean;
  disabled?: boolean;
  type?: "button" | "submit";
  onClick?: () => void;
  children: ReactNode;
};

export function Button({
  variant = "primary",
  loading = false,
  disabled = false,
  type = "button",
  onClick,
  children,
}: ButtonProps) {
  const className = `${styles.btn} ${styles[variant]}`;
  return (
    <button
      type={type}
      className={className}
      disabled={disabled || loading}
      onClick={onClick}
      data-testid="button"
      data-variant={variant}
    >
      {loading ? (
        <span className={styles.spinner} data-testid="button-spinner" />
      ) : (
        children
      )}
    </button>
  );
}
