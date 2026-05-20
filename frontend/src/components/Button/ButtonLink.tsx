import { Link, LinkProps } from "react-router-dom";
import styles from "./Button.module.css";

export type ButtonLinkProps = Omit<LinkProps, "className"> & {
  variant?: "primary" | "secondary" | "danger";
};

export function ButtonLink({
  variant = "primary",
  ...rest
}: ButtonLinkProps) {
  return (
    <Link
      className={`${styles.btn} ${styles[variant]}`}
      data-variant={variant}
      {...rest}
    />
  );
}
