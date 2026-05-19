import { useParams } from "react-router-dom";
import { ROUTES } from "../../app/routes";
import { PageHeader } from "../../components/PageHeader";
import { DetailPageGuard } from "../../components/DetailPageGuard";
import { MetaList, MetaRow } from "../../components/MetaList";
import { useProjectNameLookup } from "../projects/useProjectNameLookup";
import { useStubSlugLookup } from "../stubs/useStubSlugLookup";
import { useScanRunQuery } from "./api";
import { LifecycleActions } from "./LifecycleActions";
import { StatusBadge } from "./StatusBadge";
import { ScanRunTargetsTable } from "./ScanRunTargetsTable";
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
      {(() => {
        const livePolling = run.status === "running" || run.status === "stopping";
        return <ScanRunTargetsTable scanRunId={run.id} livePolling={livePolling} />;
      })()}
    </>
  );
}

export function ScanRunDetail() {
  const { id } = useParams();
  const query = useScanRunQuery(id);
  return (
    <DetailPageGuard
      query={query}
      options={{
        notFoundTitle: "Scan run not found",
        notFoundMessage: `No scan run matches "${id}".`,
        backTo: ROUTES.scanRuns,
        backLabel: "Back to scan runs.",
        errorTitle: "Scan run",
        errorBody: "Could not load scan run.",
      }}
    >
      {(run) => <DetailBody run={run} />}
    </DetailPageGuard>
  );
}
