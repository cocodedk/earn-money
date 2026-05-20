import { Callout } from "../../components/Callout";
import { useScanRunEvidenceQuery } from "./api";
import type { Evidence } from "../../types/api";

type Props = { scanRunId: string; livePolling: boolean };

function fmt(ts: string): string {
  return ts.slice(0, 10);
}

function dash(v: string | null): string {
  return v || "—";
}

export function ScanRunEvidencePanel({ scanRunId, livePolling }: Props) {
  const query = useScanRunEvidenceQuery(scanRunId, { livePolling });

  if (query.isError) {
    return <Callout variant="error">Could not load evidence.</Callout>;
  }
  if (!query.data) {
    return <div data-testid="evidence-loading">Loading evidence…</div>;
  }
  const { results, count, next } = query.data;
  if (count === 0) {
    return (
      <section>
        <h3>Evidence (0)</h3>
        <p data-testid="evidence-empty">No evidence yet for this run.</p>
      </section>
    );
  }

  return (
    <section>
      <h3>Evidence ({count})</h3>
      <table>
        <thead>
          <tr>
            <th>Source</th>
            <th>Target</th>
            <th>URL</th>
            <th>Method</th>
            <th>Field</th>
            <th>Matched value</th>
            <th>Created at</th>
          </tr>
        </thead>
        <tbody>
          {results.map((e: Evidence) => (
            <tr key={e.id} data-testid={`evidence-row-${e.id}`}>
              <td>{e.source}</td>
              <td><code>{e.target.slice(0, 8)}</code></td>
              <td>{dash(e.url)}</td>
              <td>{dash(e.method)}</td>
              <td>{dash(e.field)}</td>
              <td><code>{dash(e.matched_value)}</code></td>
              <td>{fmt(e.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {next !== null && (
        <p data-testid="evidence-truncation">
          Showing first {results.length} of {count} evidence
        </p>
      )}
    </section>
  );
}
