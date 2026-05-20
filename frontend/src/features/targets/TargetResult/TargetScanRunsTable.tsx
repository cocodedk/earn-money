import { Link } from "react-router-dom";
import { scanRunDetailPath } from "../../../app/routes";
import { Callout } from "../../../components/Callout";
import { Table } from "../../../components/Table";
import { useTargetScanRunsQuery } from "../api";
import type { ScanRun } from "../../../types/api";

function fmt(ts: string | null): string {
  return ts ? ts.slice(0, 19) : "—";
}

const columns = [
  { key: "id", header: "ID", cell: (r: ScanRun) => <code>{r.id.slice(0, 8)}</code> },
  { key: "status", header: "Status", cell: (r: ScanRun) => r.status },
  { key: "started_at", header: "Started at", cell: (r: ScanRun) => fmt(r.started_at) },
  { key: "finished_at", header: "Finished at", cell: (r: ScanRun) => fmt(r.finished_at) },
  { key: "findings", header: "Findings", cell: (r: ScanRun) => r.findings_count },
  {
    key: "actions",
    header: "Actions",
    cell: (r: ScanRun) => <Link to={scanRunDetailPath(r.id)}>Open</Link>,
  },
];

export function TargetScanRunsTable({ targetId }: { targetId: string }) {
  const query = useTargetScanRunsQuery(targetId);

  if (query.isError) {
    return <Callout variant="error">Could not load scan runs.</Callout>;
  }
  if (!query.data) {
    return <div data-testid="target-scan-runs-loading">Loading scan runs…</div>;
  }
  const { results, count, next } = query.data;
  return (
    <section data-testid="target-scan-runs-section">
      <h3>Latest scan runs for target ({count})</h3>
      {count === 0 ? (
        <p data-testid="target-scan-runs-empty">No scan runs yet for this target.</p>
      ) : (
        <>
          <Table<ScanRun>
            columns={columns}
            rows={results}
            rowKey={(r) => r.id}
            rowTestId={(r) => `target-scan-run-row-${r.id}`}
          />
          {next !== null && (
            <p data-testid="target-scan-runs-truncation">
              Showing first {results.length} of {count} scan runs
            </p>
          )}
        </>
      )}
    </section>
  );
}
