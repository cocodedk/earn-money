import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { ROUTES, scanRunDetailPath } from "../../app/routes";
import { ButtonLink } from "../../components/Button";
import { PageHeader } from "../../components/PageHeader";
import { Table, type TableColumn } from "../../components/Table";
import { EmptyState } from "../../components/EmptyState";
import { BackendUnreachableCallout } from "../../components/Callout";
import { byKey } from "../../lib/byKey";
import { useProjectsQuery } from "../projects/api";
import { useStubsQuery } from "../stubs/api";
import {
  usePauseScanRunMutation,
  useResumeScanRunMutation,
  useScanRunsQuery,
  useStartScanRunMutation,
  useStopScanRunMutation,
} from "./api";
import { StatusBadge } from "./StatusBadge";
import type {
  LifecycleAction,
  ScanRun,
  ScanRunStatus,
} from "../../types/api";

const VALID_ACTIONS: Record<ScanRunStatus, readonly LifecycleAction[]> = {
  queued: ["start"],
  running: ["pause", "stop"],
  paused: ["resume", "stop"],
  stopping: [],
  stopped: [],
  failed: [],
  done: [],
};

const ACTION_LABEL: Record<LifecycleAction, string> = {
  start: "Start",
  pause: "Pause",
  resume: "Resume",
  stop: "Stop",
};

function ActionButtons({ run }: { run: ScanRun }) {
  const start = useStartScanRunMutation();
  const pause = usePauseScanRunMutation();
  const resume = useResumeScanRunMutation();
  const stop = useStopScanRunMutation();
  const handlers: Record<LifecycleAction, () => void> = {
    start: () => start.mutate(run.id),
    pause: () => pause.mutate(run.id),
    resume: () => resume.mutate(run.id),
    stop: () => stop.mutate(run.id),
  };
  return (
    <div className="flex gap-2">
      <ButtonLink to={scanRunDetailPath(run.id)} variant="secondary">
        Open
      </ButtonLink>
      {VALID_ACTIONS[run.status].map((action) => (
        <button
          key={action}
          type="button"
          onClick={handlers[action]}
          className="rounded bg-gray-200 px-3 py-1 text-sm hover:bg-gray-300"
        >
          {ACTION_LABEL[action]}
        </button>
      ))}
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
  const projects = useProjectsQuery();
  const stubs = useStubsQuery();
  const navigate = useNavigate();
  const projectName = useMemo(
    () =>
      byKey(
        projects.data?.results,
        (p) => p.id,
        (p) => p.name,
        (id) => id.slice(0, 8),
      ),
    [projects.data?.results],
  );
  const stubName = useMemo(
    () =>
      byKey(
        stubs.data,
        (s) => s.slug,
        (s) => s.slug,
        (slug) => slug,
      ),
    [stubs.data],
  );
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
