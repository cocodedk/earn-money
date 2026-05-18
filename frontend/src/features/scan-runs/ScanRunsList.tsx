import { Link, useNavigate } from "react-router-dom";
import { ROUTES } from "../../app/routes";
import { ButtonLink } from "../../components/Button";
import { PageHeader } from "../../components/PageHeader";
import { Table, type TableColumn } from "../../components/Table";
import { EmptyState } from "../../components/EmptyState";
import { Callout } from "../../components/Callout";
import { StatusBadge } from "../../components/StatusBadge";
import { useScanRunsQuery } from "./api";
import { useCurrentProject } from "../../lib/useCurrentProject";
import type { ScanRun } from "../../types/api";

function formatTimestamp(value: string | null): string {
  if (!value) return "—";
  return value.slice(0, 19).replace("T", " ");
}

const columns: TableColumn<ScanRun>[] = [
  {
    key: "id",
    header: "ID",
    cell: (r) => (
      <Link
        to={ROUTES.scanRunDetail(r.id)}
        className="font-mono text-blue-700 hover:underline"
      >
        {r.id.slice(0, 8)}
      </Link>
    ),
  },
  { key: "stub_slug", header: "Stub", cell: (r) => r.stub_slug },
  {
    key: "status",
    header: "Status",
    cell: (r) => <StatusBadge status={r.status} />,
  },
  {
    key: "target_run_count",
    header: "Targets",
    cell: (r) => r.target_run_count,
  },
  { key: "findings_count", header: "Findings", cell: (r) => r.findings_count },
  {
    key: "started_at",
    header: "Started at",
    cell: (r) => formatTimestamp(r.started_at),
  },
  {
    key: "finished_at",
    header: "Finished at",
    cell: (r) => formatTimestamp(r.finished_at),
  },
];

export function ScanRunsList() {
  const { id: projectId } = useCurrentProject();
  const query = useScanRunsQuery(projectId ? { project: projectId } : {});
  const navigate = useNavigate();
  return (
    <>
      <PageHeader
        title="Scan runs"
        action={
          <ButtonLink to={ROUTES.scanRunsNew} data-testid="page-header-create">
            Create scan run
          </ButtonLink>
        }
      />
      <div className="mt-4">
        {query.isError ? (
          <Callout
            variant="error"
            title="Backend unreachable"
            action={{ label: "Retry", onClick: () => void query.refetch() }}
          >
            Could not load scan runs.
          </Callout>
        ) : (
          <Table<ScanRun>
            columns={columns}
            rows={query.data?.results ?? []}
            rowKey={(r) => r.id}
            isLoading={query.isLoading}
            emptyState={
              <EmptyState
                message="No scan runs yet."
                action={{
                  label: "Create scan run",
                  onClick: () => navigate(ROUTES.scanRunsNew),
                }}
              />
            }
          />
        )}
      </div>
    </>
  );
}
