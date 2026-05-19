import { Link, useParams } from "react-router-dom";
import { ROUTES } from "../../app/routes";
import { PageHeader } from "../../components/PageHeader";
import {
  BackendUnreachableCallout,
  Callout,
  CalloutSlot,
} from "../../components/Callout";
import { MetaList, MetaRow } from "../../components/MetaList";
import { isHttpStatus } from "../../lib/http";
import { useProjectNameLookup } from "../projects/useProjectNameLookup";
import { useStubSlugLookup } from "../stubs/useStubSlugLookup";
import { useScanRunQuery } from "./api";
import { LifecycleActions } from "./LifecycleActions";
import { StatusBadge } from "./StatusBadge";
import type { ScanRun } from "../../types/api";

function DetailBody({ run }: { run: ScanRun }) {
  const projectName = useProjectNameLookup();
  const stubName = useStubSlugLookup();
  return (
    <>
      <PageHeader
        title={`Scan run · ${run.id.slice(0, 8)}`}
        action={<LifecycleActions run={run} />}
      />
      <MetaList>
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
      </MetaList>
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
