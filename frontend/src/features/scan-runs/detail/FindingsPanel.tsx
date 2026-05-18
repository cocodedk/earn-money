import { Table, type TableColumn } from "../../../components/Table";
import { EmptyState } from "../../../components/EmptyState";
import { SeverityBadge } from "../../../components/SeverityBadge";
import type { Finding } from "../../../types/api";

const columns: TableColumn<Finding>[] = [
  { key: "title", header: "Title", cell: (r) => r.title },
  {
    key: "target",
    header: "Target",
    cell: (r) => <span className="font-mono text-xs">{r.target.slice(0, 8)}</span>,
  },
  { key: "category", header: "Category", cell: (r) => r.category },
  {
    key: "severity",
    header: "Severity",
    cell: (r) => <SeverityBadge severity={r.severity} />,
  },
  { key: "confidence", header: "Confidence", cell: (r) => r.confidence },
  { key: "status", header: "Status", cell: (r) => r.status },
  { key: "created_at", header: "Created", cell: (r) => r.created_at.slice(0, 10) },
];

export type FindingsPanelProps = {
  rows: Finding[];
  isLoading?: boolean;
};

export function FindingsPanel({ rows, isLoading }: FindingsPanelProps) {
  return (
    <Table<Finding>
      columns={columns}
      rows={rows}
      rowKey={(r) => r.id}
      isLoading={isLoading}
      emptyState={<EmptyState message="No findings yet." />}
    />
  );
}
