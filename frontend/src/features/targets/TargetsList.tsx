import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { ROUTES } from "../../app/routes";
import { ButtonLink } from "../../components/Button";
import { PageHeader } from "../../components/PageHeader";
import { Table, type TableColumn } from "../../components/Table";
import { EmptyState } from "../../components/EmptyState";
import { BackendUnreachableCallout } from "../../components/Callout";
import { useProjectNameLookup } from "../projects/useProjectNameLookup";
import { useTargetsQuery } from "./api";
import { StatusBadge } from "./StatusBadge";
import type { Target } from "../../types/api";

function buildColumns(
  projectName: (id: string) => string,
): TableColumn<Target>[] {
  return [
    { key: "base_url", header: "Base URL", cell: (t) => t.base_url },
    { key: "host", header: "Host", cell: (t) => t.host },
    { key: "ip", header: "IP", cell: (t) => t.ip ?? "—" },
    { key: "project", header: "Project", cell: (t) => projectName(t.project) },
    {
      key: "status",
      header: "Status",
      cell: (t) => <StatusBadge status={t.status} />,
    },
    {
      key: "created_at",
      header: "Created at",
      cell: (t) => t.created_at.slice(0, 10),
    },
  ];
}

export function TargetsList() {
  const targets = useTargetsQuery();
  const projectName = useProjectNameLookup();
  const navigate = useNavigate();
  const columns = useMemo(() => buildColumns(projectName), [projectName]);
  return (
    <>
      <PageHeader
        title="Targets"
        action={
          <ButtonLink to={ROUTES.targetsNew} data-testid="page-header-create">
            Create target
          </ButtonLink>
        }
      />
      <div className="mt-4">
        {targets.isError ? (
          <BackendUnreachableCallout onRetry={targets.refetch}>
            Could not load targets.
          </BackendUnreachableCallout>
        ) : (
          <Table<Target>
            columns={columns}
            rows={targets.data?.results ?? []}
            rowKey={(t) => t.id}
            isLoading={targets.isLoading}
            emptyState={
              <EmptyState
                message="No targets yet."
                action={{
                  label: "Create target",
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
