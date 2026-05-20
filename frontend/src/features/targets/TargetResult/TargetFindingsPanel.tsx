import { Callout } from "../../../components/Callout";
import { Table } from "../../../components/Table";
import { useTargetFindingsQuery } from "../api";
import type { Finding } from "../../../types/api";

function fmt(ts: string): string {
  return ts.slice(0, 10);
}

const columns = [
  { key: "title", header: "Title", cell: (f: Finding) => f.title },
  { key: "scan_run", header: "Scan run", cell: (f: Finding) => <code>{f.scan_run.slice(0, 8)}</code> },
  { key: "category", header: "Category", cell: (f: Finding) => f.category },
  { key: "severity", header: "Severity", cell: (f: Finding) => f.severity },
  { key: "confidence", header: "Confidence", cell: (f: Finding) => f.confidence || "—" },
  { key: "status", header: "Status", cell: (f: Finding) => f.status },
  { key: "created_at", header: "Created at", cell: (f: Finding) => fmt(f.created_at) },
];

export function TargetFindingsPanel({ targetId }: { targetId: string }) {
  const query = useTargetFindingsQuery(targetId);

  if (query.isError) {
    return <Callout variant="error">Could not load findings.</Callout>;
  }
  if (!query.data) {
    return <div data-testid="target-findings-loading">Loading findings…</div>;
  }
  const { results, count, next } = query.data;
  return (
    <section data-testid="target-findings-section">
      <h3>Findings for target ({count})</h3>
      {count === 0 ? (
        <p data-testid="target-findings-empty">No findings yet for this target.</p>
      ) : (
        <>
          <Table<Finding>
            columns={columns}
            rows={results}
            rowKey={(f) => f.id}
            rowTestId={(f) => `target-finding-row-${f.id}`}
          />
          {next !== null && (
            <p data-testid="target-findings-truncation">
              Showing first {results.length} of {count} findings
            </p>
          )}
        </>
      )}
    </section>
  );
}
