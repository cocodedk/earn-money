import { Callout } from "../../../components/Callout";
import { Table } from "../../../components/Table";
import { useTargetEvidenceQuery } from "../api";
import type { Evidence } from "../../../types/api";

function fmt(ts: string): string {
  return ts.slice(0, 10);
}

function dash(v: string | null): string {
  return v || "—";
}

const columns = [
  { key: "source", header: "Source", cell: (e: Evidence) => e.source },
  { key: "scan_run", header: "Scan run", cell: (e: Evidence) => <code>{e.scan_run.slice(0, 8)}</code> },
  { key: "url", header: "URL", cell: (e: Evidence) => dash(e.url) },
  { key: "method", header: "Method", cell: (e: Evidence) => dash(e.method) },
  { key: "field", header: "Field", cell: (e: Evidence) => dash(e.field) },
  { key: "matched_value", header: "Matched value", cell: (e: Evidence) => <code>{dash(e.matched_value)}</code> },
  { key: "created_at", header: "Created at", cell: (e: Evidence) => fmt(e.created_at) },
];

export function TargetEvidencePanel({ targetId }: { targetId: string }) {
  const query = useTargetEvidenceQuery(targetId);

  if (query.isError) {
    return <Callout variant="error">Could not load evidence.</Callout>;
  }
  if (!query.data) {
    return <div data-testid="target-evidence-loading">Loading evidence…</div>;
  }
  const { results, count, next } = query.data;
  return (
    <section data-testid="target-evidence-section">
      <h3>Evidence for target ({count})</h3>
      {count === 0 ? (
        <p data-testid="target-evidence-empty">No evidence yet for this target.</p>
      ) : (
        <>
          <Table<Evidence>
            columns={columns}
            rows={results}
            rowKey={(e) => e.id}
            rowTestId={(e) => `target-evidence-row-${e.id}`}
          />
          {next !== null && (
            <p data-testid="target-evidence-truncation">
              Showing first {results.length} of {count} evidence
            </p>
          )}
        </>
      )}
    </section>
  );
}
