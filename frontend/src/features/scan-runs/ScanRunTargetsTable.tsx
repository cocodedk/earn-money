import { useScanRunTargetRunsQuery } from "./api";
import { StatusBadge } from "./StatusBadge";
import { Callout } from "../../components/Callout";
import { Table } from "../../components/Table";
import type { ScanTargetRun } from "../../types/api";

export type ScanRunTargetsTableProps = {
  scanRunId: string;
  livePolling: boolean;
};

const fmt = (ts: string | null) => (ts ? ts.slice(0, 19) : "—");

const columns = [
  {
    key: "target",
    header: "Target",
    cell: (r: ScanTargetRun) => (
      <>
        <div>{r.target_host}</div>
        <div>{r.target_base_url}</div>
      </>
    ),
  },
  { key: "status", header: "Status", cell: (r: ScanTargetRun) => <StatusBadge status={r.status} /> },
  { key: "started_at", header: "Started at", cell: (r: ScanTargetRun) => fmt(r.started_at) },
  { key: "finished_at", header: "Finished at", cell: (r: ScanTargetRun) => fmt(r.finished_at) },
  { key: "findings", header: "Findings", cell: (r: ScanTargetRun) => r.findings_count },
  { key: "evidence", header: "Evidence", cell: (r: ScanTargetRun) => r.evidence_count },
];

export function ScanRunTargetsTable({ scanRunId, livePolling }: ScanRunTargetsTableProps) {
  const query = useScanRunTargetRunsQuery(scanRunId, { livePolling });

  if (query.isError) {
    return (
      <Callout variant="error">Could not load target rows. Refresh to retry.</Callout>
    );
  }
  if (!query.data) {
    return <div data-testid="targets-loading">Loading targets…</div>;
  }
  const { results, count, next } = query.data;
  if (count === 0) {
    return <div data-testid="targets-empty">No targets in this scan run.</div>;
  }
  return (
    <section>
      <Table<ScanTargetRun>
        columns={columns}
        rows={results}
        rowKey={(r) => r.id}
        rowTestId={(r) => `target-run-row-${r.id}`}
      />
      {next !== null && (
        <p data-testid="targets-truncation">
          Showing first {results.length} of {count} targets
        </p>
      )}
    </section>
  );
}
