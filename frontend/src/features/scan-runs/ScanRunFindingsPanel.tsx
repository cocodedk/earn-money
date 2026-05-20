import { Callout } from "../../components/Callout";
import { useScanRunFindingsQuery } from "./api";
import type { Finding } from "../../types/api";

type Props = { scanRunId: string; livePolling: boolean };

function fmt(ts: string): string {
  return ts.slice(0, 10);
}

export function ScanRunFindingsPanel({ scanRunId, livePolling }: Props) {
  const query = useScanRunFindingsQuery(scanRunId, { livePolling });

  if (query.isError) {
    return <Callout variant="error">Could not load findings.</Callout>;
  }
  if (!query.data) {
    return <div data-testid="findings-loading">Loading findings…</div>;
  }
  const { results, count, next } = query.data;
  if (count === 0) {
    return (
      <section>
        <h3>Findings (0)</h3>
        <p data-testid="findings-empty">No findings yet for this run.</p>
      </section>
    );
  }

  return (
    <section>
      <h3>Findings ({count})</h3>
      <table>
        <thead>
          <tr>
            <th>Title</th>
            <th>Target</th>
            <th>Category</th>
            <th>Severity</th>
            <th>Confidence</th>
            <th>Status</th>
            <th>Created at</th>
          </tr>
        </thead>
        <tbody>
          {results.map((f: Finding) => (
            <tr key={f.id} data-testid={`finding-row-${f.id}`}>
              <td>{f.title}</td>
              <td><code>{f.target.slice(0, 8)}</code></td>
              <td>{f.category}</td>
              <td>{f.severity}</td>
              <td>{f.confidence}</td>
              <td>{f.status}</td>
              <td>{fmt(f.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {next !== null && (
        <p data-testid="findings-truncation">
          Showing first {results.length} of {count} findings
        </p>
      )}
    </section>
  );
}
