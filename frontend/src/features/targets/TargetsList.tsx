import { useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ROUTES, targetResultPath } from "../../app/routes";
import { ButtonLink } from "../../components/Button";
import { PageHeader } from "../../components/PageHeader";
import { Table, type TableColumn } from "../../components/Table";
import { EmptyState } from "../../components/EmptyState";
import { ListPageGuard } from "../../components/ListPageGuard";
import { useProjectNameLookup } from "../projects/useProjectNameLookup";
import { useTargetsQuery } from "./api";
import { StatusBadge } from "./StatusBadge";
import { TargetsFiltersBar, applyTargetFilters } from "./TargetsFiltersBar";
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
    {
      key: "actions",
      header: "Actions",
      cell: (t) => (
        <ButtonLink to={targetResultPath(t.id)} variant="secondary">
          Open results
        </ButtonLink>
      ),
    },
  ];
}

export function TargetsList() {
  const targets = useTargetsQuery();
  const projectName = useProjectNameLookup();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const columns = useMemo(() => buildColumns(projectName), [projectName]);
  const rows = targets.data?.results ?? [];
  const filtered = useMemo(
    () => applyTargetFilters(rows, params),
    [rows, params],
  );
  const emptyState =
    rows.length === 0 ? (
      <EmptyState
        message="No targets yet."
        action={{
          label: "Create target",
          onClick: () => navigate(ROUTES.targetsNew),
        }}
      />
    ) : (
      <EmptyState message="No targets match the current filters." />
    );
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
      <TargetsFiltersBar />
      <ListPageGuard query={targets} errorBody="Could not load targets.">
        <Table<Target>
          columns={columns}
          rows={filtered}
          rowKey={(t) => t.id}
          isLoading={targets.isLoading}
          emptyState={emptyState}
        />
      </ListPageGuard>
    </>
  );
}
