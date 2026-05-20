import { ReactNode } from "react";
import styles from "./Table.module.css";
import { TableSkeleton } from "./TableSkeleton";

export type TableColumn<T> = {
  key: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  width?: string;
};

export type TableProps<T> = {
  columns: TableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  rowTestId?: (row: T) => string;
  isLoading?: boolean;
  emptyState?: ReactNode;
};

export function Table<T>({
  columns,
  rows,
  rowKey,
  rowTestId,
  isLoading,
  emptyState,
}: TableProps<T>) {
  if (!isLoading && rows.length === 0 && emptyState) {
    return emptyState;
  }
  return (
    <table className={styles.table} data-testid="table">
      <thead>
        <tr>
          {columns.map((c) => (
            <th key={c.key} style={c.width ? { width: c.width } : undefined}>
              {c.header}
            </th>
          ))}
        </tr>
      </thead>
      {isLoading ? (
        <TableSkeleton columnCount={columns.length} rowCount={5} />
      ) : (
        <tbody>
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              data-testid={rowTestId ? rowTestId(row) : undefined}
            >
              {columns.map((c) => (
                <td key={c.key}>{c.cell(row)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      )}
    </table>
  );
}
