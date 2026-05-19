import { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { ROUTES } from "../../app/routes";
import { PageHeader } from "../../components/PageHeader";
import {
  BackendUnreachableCallout,
  Callout,
  CalloutSlot,
} from "../../components/Callout";
import { byKey } from "../../lib/byKey";
import { isHttpStatus } from "../../lib/http";
import { useProjectsQuery } from "../projects/api";
import { useStubsQuery } from "../stubs/api";
import { useScanRunQuery } from "./api";
import { ACTION_LABEL, useScanRunActions } from "./useScanRunActions";
import { StatusBadge } from "./StatusBadge";
import type { ScanRun } from "../../types/api";

function MetaRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex gap-4 text-sm">
      <span className="w-32 font-medium text-gray-600">{label}</span>
      <span>{children}</span>
    </div>
  );
}

function HeaderActions({ run }: { run: ScanRun }) {
  const { visibleActions, handlers } = useScanRunActions(run);
  if (visibleActions.length === 0) return null;
  return (
    <div className="flex gap-2">
      {visibleActions.map((action) => (
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

function DetailBody({ run }: { run: ScanRun }) {
  const projects = useProjectsQuery();
  const stubs = useStubsQuery();
  const projectName = byKey(
    projects.data?.results,
    (p) => p.id,
    (p) => p.name,
    (id) => id.slice(0, 8),
  );
  const stubName = byKey(
    stubs.data,
    (s) => s.slug,
    (s) => s.slug,
    (slug) => slug,
  );
  return (
    <>
      <PageHeader
        title={`Scan run · ${run.id.slice(0, 8)}`}
        action={<HeaderActions run={run} />}
      />
      <div className="mt-4 flex flex-col gap-2">
        <MetaRow label="ID">
          <code>{run.id}</code>
        </MetaRow>
        <MetaRow label="Project">{projectName(run.project)}</MetaRow>
        <MetaRow label="Stub">{stubName(run.stub_slug)}</MetaRow>
        <MetaRow label="Status">
          <StatusBadge status={run.status} />
        </MetaRow>
        <MetaRow label="Started at">
          {run.started_at ? run.started_at.slice(0, 19) : "—"}
        </MetaRow>
        <MetaRow label="Finished at">
          {run.finished_at ? run.finished_at.slice(0, 19) : "—"}
        </MetaRow>
      </div>
    </>
  );
}

export function ScanRunDetail() {
  const { id } = useParams();
  const query = useScanRunQuery(id);

  if (isHttpStatus(query.error, 404)) {
    return (
      <>
        <PageHeader title="Scan run not found" />
        <CalloutSlot>
          <Callout variant="info">
            No scan run matches "{id}".{" "}
            <Link to={ROUTES.scanRuns}>Back to scan runs.</Link>
          </Callout>
        </CalloutSlot>
      </>
    );
  }
  if (query.isError) {
    return (
      <>
        <PageHeader title="Scan run" />
        <CalloutSlot>
          <BackendUnreachableCallout>
            Could not load scan run.
          </BackendUnreachableCallout>
        </CalloutSlot>
      </>
    );
  }
  if (!query.data) {
    return <PageHeader title="Loading…" />;
  }
  return <DetailBody run={query.data} />;
}
