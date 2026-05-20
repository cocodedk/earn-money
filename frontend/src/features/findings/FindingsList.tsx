import { Link, useSearchParams } from "react-router-dom";
import { PageHeader } from "../../components/PageHeader";
import { Table, type TableColumn } from "../../components/Table";
import { EmptyState } from "../../components/EmptyState";
import { ListPageGuard } from "../../components/ListPageGuard";
import {
  findingDetailPath,
  stubDetailPath,
  targetResultPath,
} from "../../app/routes";
import {
  FILTER_PARAM_KEYS,
  FindingsFiltersBar,
} from "./FindingsFiltersBar";
import { useFindingsListQuery, type FindingsFilters } from "./api";
import type { Finding } from "../../types/api";

function readFilters(params: URLSearchParams): FindingsFilters {
  const out: Record<string, string> = {};
  for (const key of FILTER_PARAM_KEYS) {
    const v = params.get(key);
    if (v) out[key] = v;
  }
  return out as FindingsFilters;
}

function evidenceForFindingHref(id: string) {
  return `/evidence?finding=${id}`;
}

const columns: TableColumn<Finding>[] = [
  {
    key: "title",
    header: "Title",
    cell: (r) => (
      <Link to={findingDetailPath(r.id)}>{r.title}</Link>
    ),
  },
  {
    key: "target",
    header: "Target",
    cell: (r) => (
      <Link to={targetResultPath(r.target)}>
        <code>{r.target.slice(0, 8)}</code>
      </Link>
    ),
  },
  {
    key: "stub",
    header: "Stub",
    cell: (r) => (
      <Link to={stubDetailPath(r.stub_slug)}>{r.stub_slug}</Link>
    ),
  },
  { key: "category", header: "Category", cell: (r) => r.category },
  { key: "severity", header: "Severity", cell: (r) => r.severity },
  {
    key: "confidence",
    header: "Confidence",
    cell: (r) => r.confidence || "—",
  },
  { key: "status", header: "Status", cell: (r) => r.status },
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
        <Link to={findingDetailPath(r.id)}>Open finding</Link>
        <Link to={evidenceForFindingHref(r.id)}>Open evidence</Link>
      </div>
    ),
  },
];

export function FindingsList() {
  const [params] = useSearchParams();
  const filters = readFilters(params);
  const query = useFindingsListQuery(filters);
  const rows = query.data?.results ?? [];

  return (
    <>
      <PageHeader title="Findings" />
      <FindingsFiltersBar />
      <ListPageGuard query={query} errorBody="Could not load findings.">
        <Table<Finding>
          columns={columns}
          rows={rows}
          rowKey={(r) => r.id}
          rowTestId={(r) => `finding-row-${r.id}`}
          isLoading={query.isLoading}
          emptyState={
            <EmptyState message="No findings match the current filters." />
          }
        />
        {query.data?.next != null && (
          <p data-testid="findings-truncation">
            Showing first {rows.length} of {query.data.count} findings
          </p>
        )}
      </ListPageGuard>
    </>
  );
}
