import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { ROUTES, scanRunDetailPath } from "../../app/routes";
import { ButtonLink } from "../../components/Button";
import { PageHeader } from "../../components/PageHeader";
import { Table, type TableColumn } from "../../components/Table";
import { EmptyState } from "../../components/EmptyState";
import { BackendUnreachableCallout } from "../../components/Callout";
import { useProjectNameLookup } from "../projects/useProjectNameLookup";
import { useStubSlugLookup } from "../stubs/useStubSlugLookup";
import { useScanRunsQuery } from "./api";
import { LifecycleActions } from "./LifecycleActions";
import { StatusBadge } from "./StatusBadge";
import type { ScanRun } from "../../types/api";

function ActionButtons({ run }: { run: ScanRun }) {
  return (
    <div className="flex gap-2">
      <ButtonLink to={scanRunDetailPath(run.id)} variant="secondary">
        Open
      </ButtonLink>
      <LifecycleActions run={run} />
    </div>
  );
}

function buildColumns(
  projectName: (id: string) => string,
  stubName: (slug: string) => string,
): TableColumn<ScanRun>[] {
  return [
    { key: "id", header: "ID", cell: (r) => r.id.slice(0, 8) },
    {
      key: "project",
      header: "Project",
      cell: (r) => projectName(r.project),
    },
    { key: "stub", header: "Stub", cell: (r) => stubName(r.stub_slug) },
    {
      key: "status",
      header: "Status",
      cell: (r) => <StatusBadge status={r.status} />,
    },
    {
      key: "targets",
      header: "Targets",
      cell: (r) => r.target_run_count,
    },
    {
      key: "findings",
      header: "Findings",
      cell: (r) => r.findings_count,
    },
    {
      key: "started_at",
      header: "Started at",
      cell: (r) => (r.started_at ? r.started_at.slice(0, 19) : "—"),
    },
    {
      key: "finished_at",
      header: "Finished at",
      cell: (r) => (r.finished_at ? r.finished_at.slice(0, 19) : "—"),
    },
    {
      key: "actions",
      header: "Actions",
      cell: (r) => <ActionButtons run={r} />,
    },
  ];
}

export function ScanRunsList() {
  const runs = useScanRunsQuery();
  const projectName = useProjectNameLookup();
  const stubName = useStubSlugLookup();
  const navigate = useNavigate();
  const columns = useMemo(
    () => buildColumns(projectName, stubName),
    [projectName, stubName],
  );
  return (
    <>
      <PageHeader title="Scan runs" />
      <div className="mt-4">
        {runs.isError ? (
          <BackendUnreachableCallout onRetry={runs.refetch}>
            Could not load scan runs.
          </BackendUnreachableCallout>
        ) : (
          <Table<ScanRun>
            columns={columns}
            rows={runs.data?.results ?? []}
            rowKey={(r) => r.id}
            isLoading={runs.isLoading}
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
