import { Table, type TableColumn } from "../../../components/Table";
import { EmptyState } from "../../../components/EmptyState";
import type { Evidence } from "../../../types/api";

const columns: TableColumn<Evidence>[] = [
  { key: "source", header: "Source", cell: (r) => r.source },
  {
    key: "target",
    header: "Target",
    cell: (r) => <span className="font-mono text-xs">{r.target.slice(0, 8)}</span>,
  },
  { key: "url", header: "URL", cell: (r) => r.url ?? "—" },
  { key: "method", header: "Method", cell: (r) => r.method ?? "—" },
  { key: "field", header: "Field", cell: (r) => r.field ?? "—" },
  {
    key: "matched_value",
    header: "Matched value",
    cell: (r) => (
      <span className="font-mono text-xs">{r.matched_value ?? "—"}</span>
    ),
  },
  { key: "created_at", header: "Created", cell: (r) => r.created_at.slice(0, 10) },
];

export type EvidencePanelProps = {
  rows: Evidence[];
  isLoading?: boolean;
};

export function EvidencePanel({ rows, isLoading }: EvidencePanelProps) {
  return (
    <Table<Evidence>
      columns={columns}
      rows={rows}
      rowKey={(r) => r.id}
      isLoading={isLoading}
      emptyState={<EmptyState message="No evidence yet." />}
    />
  );
}
