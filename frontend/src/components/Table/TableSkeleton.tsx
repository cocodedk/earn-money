import styles from "./Table.module.css";

export type TableSkeletonProps = { columnCount: number; rowCount?: number };

export function TableSkeleton({ columnCount, rowCount = 5 }: TableSkeletonProps) {
  return (
    <tbody>
      {Array.from({ length: rowCount }).map((_, r) => (
        <tr key={r} data-testid="skeleton-row" className={styles.skeletonRow}>
          {Array.from({ length: columnCount }).map((__, c) => (
            <td key={c}>
              <span className={styles.skeletonCell} />
            </td>
          ))}
        </tr>
      ))}
    </tbody>
  );
}
