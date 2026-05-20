import { Callout } from "../../components/Callout";
import { Table } from "../../components/Table";
import { useScanRunFindingsQuery } from "./api";
import type { Finding } from "../../types/api";

type Props = { scanRunId: string; livePolling: boolean };

function fmt(ts: string): string {
  return ts.slice(0, 10);
}

const columns = [
  { key: "title", header: "Title", cell: (f: Finding) => f.title },
  { key: "target", header: "Target", cell: (f: Finding) => <code>{f.target.slice(0, 8)}</code> },
  { key: "category", header: "Category", cell: (f: Finding) => f.category },
  { key: "severity", header: "Severity", cell: (f: Finding) => f.severity },
  { key: "confidence", header: "Confidence", cell: (f: Finding) => f.confidence || "—" },
  { key: "status", header: "Status", cell: (f: Finding) => f.status },
  { key: "created_at", header: "Created at", cell: (f: Finding) => fmt(f.created_at) },
];

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
      <Table<Finding>
        columns={columns}
        rows={results}
        rowKey={(f) => f.id}
        rowTestId={(f) => `finding-row-${f.id}`}
      />
      {next !== null && (
        <p data-testid="findings-truncation">
          Showing first {results.length} of {count} findings
        </p>
      )}
    </section>
  );
}
