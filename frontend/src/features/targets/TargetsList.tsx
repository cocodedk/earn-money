import { useNavigate } from "react-router-dom";
import { ROUTES } from "../../app/routes";
import { ButtonLink } from "../../components/Button";
import { PageHeader } from "../../components/PageHeader";
import { Table, type TableColumn } from "../../components/Table";
import { EmptyState } from "../../components/EmptyState";
import { Callout } from "../../components/Callout";
import { StatusBadge } from "../../components/StatusBadge";
import { useTargetsQuery } from "./api";
import { useCurrentProject } from "../../lib/useCurrentProject";
import type { Target } from "../../types/api";

const columns: TableColumn<Target>[] = [
  { key: "base_url", header: "Base URL", cell: (r) => r.base_url },
  { key: "host", header: "Host", cell: (r) => r.host ?? "—" },
  { key: "ip", header: "IP", cell: (r) => r.ip ?? "—" },
  {
    key: "status",
    header: "Status",
    cell: (r) => <StatusBadge status={r.status} />,
  },
  {
    key: "created_at",
    header: "Created at",
    cell: (r) => r.created_at.slice(0, 10),
  },
];

export function TargetsList() {
  const { id: projectId } = useCurrentProject();
  const query = useTargetsQuery(projectId);
  const navigate = useNavigate();

  if (!projectId) {
    return (
      <>
        <PageHeader title="Targets" />
        <div className="mt-4">
          <Callout variant="info" title="Select a project first">
            Targets are scoped to the current project. Open the Projects page and set one as current.
          </Callout>
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Targets"
        action={
          <ButtonLink to={ROUTES.targetsNew} data-testid="page-header-create">
            Add target
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
            Could not load targets.
          </Callout>
        ) : (
          <Table<Target>
            columns={columns}
            rows={query.data?.results ?? []}
            rowKey={(r) => r.id}
            isLoading={query.isLoading}
            emptyState={
              <EmptyState
                message="No targets yet."
                action={{
                  label: "Add target",
                  onClick: () => navigate(ROUTES.targetsNew),
                }}
              />
            }
          />
        )}
      </div>
    </>
  );
}
