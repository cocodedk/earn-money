import { ReactNode } from "react";
import styles from "./PageHeader.module.css";

export type PageHeaderProps = {
  title: string;
  action?: ReactNode;
};

export function PageHeader({ title, action }: PageHeaderProps) {
  return (
    <div className={styles.header}>
      <h1 className={styles.title}>{title}</h1>
      {action && <div className={styles.action}>{action}</div>}
    </div>
  );
}
