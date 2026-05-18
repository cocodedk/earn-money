import { Link } from "react-router-dom";
import { PageHeader } from "../../components/PageHeader";
import { Table, type TableColumn } from "../../components/Table";
import { EmptyState } from "../../components/EmptyState";
import { Callout } from "../../components/Callout";
import { StatusBadge } from "../../components/StatusBadge";
import type { StatusBadgeStatus } from "../../components/StatusBadge";
import { useStubsQuery } from "./api";
import type { Stub } from "../../types/api";

function stubStatusToBadge(status: Stub["status"]): StatusBadgeStatus {
  if (status === "done") return "done";
  if (status === "in_progress") return "running";
  return "queued";
}

const columns: TableColumn<Stub>[] = [
  { key: "slug", header: "Slug", cell: (r) => r.slug },
  { key: "phase", header: "Phase", cell: (r) => r.phase_title },
  {
    key: "title",
    header: "Title",
    cell: (r) => (
      <Link to={`/stubs/${r.slug}`} className="text-blue-700 hover:underline">
        {r.title}
      </Link>
    ),
  },
  { key: "category", header: "Category", cell: (r) => r.category },
  {
    key: "status",
    header: "Status",
    cell: (r) => <StatusBadge status={stubStatusToBadge(r.status)} />,
  },
  { key: "fixture", header: "Fixture", cell: (r) => r.fixture ?? "—" },
];

export function StubsList() {
  const query = useStubsQuery();
  return (
    <>
      <PageHeader title="Stubs" />
      <div className="mt-4">
        {query.isError ? (
          <Callout
            variant="error"
            title="Backend unreachable"
            action={{ label: "Retry", onClick: () => void query.refetch() }}
          >
            Could not load stubs.
          </Callout>
        ) : (
          <Table<Stub>
            columns={columns}
            rows={query.data ?? []}
            rowKey={(r) => r.slug}
            isLoading={query.isLoading}
            emptyState={<EmptyState message="No stubs available." />}
          />
        )}
      </div>
    </>
  );
}
