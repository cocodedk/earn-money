import { Callout } from "../../components/Callout";
import { Table } from "../../components/Table";
import { useScanRunEvidenceQuery } from "./api";
import type { Evidence } from "../../types/api";

type Props = { scanRunId: string; livePolling: boolean };

function fmt(ts: string): string {
  return ts.slice(0, 10);
}

function dash(v: string | null): string {
  return v || "—";
}

const columns = [
  { key: "source", header: "Source", cell: (e: Evidence) => e.source },
  { key: "target", header: "Target", cell: (e: Evidence) => <code>{e.target.slice(0, 8)}</code> },
  { key: "url", header: "URL", cell: (e: Evidence) => dash(e.url) },
  { key: "method", header: "Method", cell: (e: Evidence) => dash(e.method) },
  { key: "field", header: "Field", cell: (e: Evidence) => dash(e.field) },
  { key: "matched_value", header: "Matched value", cell: (e: Evidence) => <code>{dash(e.matched_value)}</code> },
  { key: "created_at", header: "Created at", cell: (e: Evidence) => fmt(e.created_at) },
];

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
      <Table<Evidence>
        columns={columns}
        rows={results}
        rowKey={(e) => e.id}
        rowTestId={(e) => `evidence-row-${e.id}`}
      />
      {next !== null && (
        <p data-testid="evidence-truncation">
          Showing first {results.length} of {count} evidence
        </p>
      )}
    </section>
  );
}
