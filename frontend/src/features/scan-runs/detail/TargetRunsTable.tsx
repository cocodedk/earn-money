import { Table, type TableColumn } from "../../../components/Table";
import { EmptyState } from "../../../components/EmptyState";
import { StatusBadge } from "../../../components/StatusBadge";
import type { TargetRun } from "../../../types/api";

function formatTimestamp(value: string | null): string {
  if (!value) return "—";
  return value.slice(11, 19);
}

const columns: TableColumn<TargetRun>[] = [
  { key: "target_base_url", header: "Target", cell: (r) => r.target_base_url },
  {
    key: "status",
    header: "Status",
    cell: (r) => <StatusBadge status={r.status} />,
  },
  { key: "started_at", header: "Started", cell: (r) => formatTimestamp(r.started_at) },
  { key: "finished_at", header: "Finished", cell: (r) => formatTimestamp(r.finished_at) },
  { key: "findings_count", header: "Findings", cell: (r) => r.findings_count },
  { key: "evidence_count", header: "Evidence", cell: (r) => r.evidence_count },
];

export type TargetRunsTableProps = {
  rows: TargetRun[];
  isLoading?: boolean;
};

export function TargetRunsTable({ rows, isLoading }: TargetRunsTableProps) {
  return (
    <Table<TargetRun>
      columns={columns}
      rows={rows}
      rowKey={(r) => r.id}
      isLoading={isLoading}
      emptyState={<EmptyState message="No target runs yet." />}
    />
  );
}
