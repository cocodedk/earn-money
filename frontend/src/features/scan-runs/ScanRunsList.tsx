import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { ROUTES, scanRunDetailPath } from "../../app/routes";
import { ButtonLink } from "../../components/Button";
import { PageHeader } from "../../components/PageHeader";
import { Table, type TableColumn } from "../../components/Table";
import { EmptyState } from "../../components/EmptyState";
import { BackendUnreachableCallout } from "../../components/Callout";
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
  Project,
  ScanRun,
  ScanRunStatus,
  StubSummary,
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

function nameLookup(projects: Project[] | undefined) {
  const byId = new Map<string, string>();
  for (const p of projects ?? []) byId.set(p.id, p.name);
  return (id: string) => byId.get(id) ?? id.slice(0, 8);
}

function stubLookup(stubs: StubSummary[] | undefined) {
  const bySlug = new Map<string, string>();
  for (const s of stubs ?? []) bySlug.set(s.slug, s.slug);
  return (slug: string) => bySlug.get(slug) ?? slug;
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
    () => nameLookup(projects.data?.results),
    [projects.data?.results],
  );
  const stubName = useMemo(() => stubLookup(stubs.data), [stubs.data]);
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
