import { ReactNode } from "react";
import styles from "./MetaList.module.css";

export function MetaList({ children }: { children: ReactNode }) {
  return <div className={styles.list}>{children}</div>;
}

export function MetaRow({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <>
      <span className={styles.label}>{label}</span>
      <span className={styles.value}>{children}</span>
    </>
  );
}
