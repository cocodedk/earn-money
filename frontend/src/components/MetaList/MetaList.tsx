import { ReactNode } from "react";
import styles from "./MetaList.module.css";

// Children must be <MetaRow> only — they are flattened into a 2-col CSS grid
// by the parent. Interstitial nodes break the label/value rhythm.
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
