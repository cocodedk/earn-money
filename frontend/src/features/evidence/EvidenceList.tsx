import { Link, useSearchParams } from "react-router-dom";
import { PageHeader } from "../../components/PageHeader";
import { Table, type TableColumn } from "../../components/Table";
import { EmptyState } from "../../components/EmptyState";
import { ListPageGuard } from "../../components/ListPageGuard";
import {
  evidenceDetailPath,
  findingDetailPath,
  targetResultPath,
} from "../../app/routes";
import {
  FILTER_PARAM_KEYS,
  EvidenceFiltersBar,
} from "./EvidenceFiltersBar";
import { useEvidenceListQuery, type EvidenceFilters } from "./api";
import type { Evidence } from "../../types/api";

const dash = (v: string | null) => v || "—";

function readFilters(params: URLSearchParams): EvidenceFilters {
  const out: Record<string, string> = {};
  for (const key of FILTER_PARAM_KEYS) {
    const v = params.get(key);
    if (v) out[key] = v;
  }
  return out as EvidenceFilters;
}

const columns: TableColumn<Evidence>[] = [
  {
    key: "target",
    header: "Target",
    cell: (r) => (
      <Link to={targetResultPath(r.target)}>
        <code>{r.target.slice(0, 8)}</code>
      </Link>
    ),
  },
  { key: "source", header: "Source", cell: (r) => r.source },
  { key: "url", header: "URL", cell: (r) => dash(r.url) },
  { key: "method", header: "Method", cell: (r) => dash(r.method) },
  { key: "field", header: "Field", cell: (r) => dash(r.field) },
  {
    key: "matched_value",
    header: "Matched value",
    cell: (r) => <code>{dash(r.matched_value)}</code>,
  },
  {
    key: "created_at",
    header: "Created at",
    cell: (r) => r.created_at.slice(0, 19),
  },
  {
    key: "actions",
    header: "Actions",
    cell: (r) => (
      <div className="flex gap-2">
        <Link to={evidenceDetailPath(r.id)}>Open evidence</Link>
        {r.finding && (
          <Link
            to={findingDetailPath(r.finding)}
            data-testid={`evidence-finding-link-${r.id}`}
          >
            Open finding
          </Link>
        )}
      </div>
    ),
  },
];

export function EvidenceList() {
  const [params] = useSearchParams();
  const filters = readFilters(params);
  const query = useEvidenceListQuery(filters);
  const rows = query.data?.results ?? [];

  return (
    <>
      <PageHeader title="Evidence" />
      <EvidenceFiltersBar />
      <ListPageGuard query={query} errorBody="Could not load evidence.">
        <Table<Evidence>
          columns={columns}
          rows={rows}
          rowKey={(r) => r.id}
          rowTestId={(r) => `evidence-row-${r.id}`}
          isLoading={query.isLoading}
          emptyState={
            <EmptyState message="No evidence matches the current filters." />
          }
        />
        {query.data?.next != null && (
          <p data-testid="evidence-truncation">
            Showing first {rows.length} of {query.data.count} evidence records
          </p>
        )}
      </ListPageGuard>
    </>
  );
}
