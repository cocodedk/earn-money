import { useScanRunTargetRunsQuery } from "./api";
import { StatusBadge } from "./StatusBadge";
import { Callout } from "../../components/Callout";
import type { ScanTargetRun } from "../../types/api";

export type ScanRunTargetsTableProps = {
  scanRunId: string;
  livePolling: boolean;
};

const fmt = (ts: string | null) => (ts ? ts.slice(0, 19) : "—");

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
      <table>
        <thead>
          <tr>
            <th>Target</th>
            <th>Status</th>
            <th>Started at</th>
            <th>Finished at</th>
            <th>Findings</th>
            <th>Evidence</th>
          </tr>
        </thead>
        <tbody>
          {results.map((r: ScanTargetRun) => (
            <tr key={r.id} data-testid={`target-run-row-${r.id}`}>
              <td>
                <div>{r.target_host}</div>
                <div>{r.target_base_url}</div>
              </td>
              <td><StatusBadge status={r.status} /></td>
              <td>{fmt(r.started_at)}</td>
              <td>{fmt(r.finished_at)}</td>
              <td>{r.findings_count}</td>
              <td>{r.evidence_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {next !== null && (
        <p data-testid="targets-truncation">
          Showing first {results.length} of {count} targets
        </p>
      )}
    </section>
  );
}
