import { useParams } from "react-router-dom";
import { PageHeader } from "../../components/PageHeader";
import { Callout } from "../../components/Callout";
import {
  useScanRunDetailQuery,
  useScanRunFindingsQuery,
  useScanRunEvidenceQuery,
  useScanRunTargetRunsQuery,
} from "./api";
import { ScanRunHeader } from "./detail/ScanRunHeader";
import { LifecycleControls } from "./detail/LifecycleControls";
import { TargetRunsTable } from "./detail/TargetRunsTable";
import { FindingsPanel } from "./detail/FindingsPanel";
import { EvidencePanel } from "./detail/EvidencePanel";
import { LiveEventsPanel } from "./LiveEventsPanel";

export function ScanRunDetail() {
  const { id = null } = useParams();
  const runQuery = useScanRunDetailQuery(id);
  const targetRunsQuery = useScanRunTargetRunsQuery(id);
  const findingsQuery = useScanRunFindingsQuery(id);
  const evidenceQuery = useScanRunEvidenceQuery(id);

  if (!id || runQuery.isError) {
    return (
      <>
        <PageHeader title="Scan run" />
        <div className="mt-4">
          <Callout variant="error" title="Not found">
            This scan run could not be loaded.
          </Callout>
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Scan run"
        action={runQuery.data && <LifecycleControls scanRun={runQuery.data} />}
      />
      <div className="mt-4 flex flex-col gap-6">
        {runQuery.data && <ScanRunHeader scanRun={runQuery.data} />}
        <section>
          <h2 className="text-lg font-medium mb-2">Targets</h2>
          <TargetRunsTable
            isLoading={targetRunsQuery.isLoading}
            rows={targetRunsQuery.data?.results ?? []}
          />
        </section>
        <section>
          <h2 className="text-lg font-medium mb-2">Live events</h2>
          <LiveEventsPanel scanRunId={id} />
        </section>
        <section>
          <h2 className="text-lg font-medium mb-2">Findings</h2>
          <FindingsPanel
            isLoading={findingsQuery.isLoading}
            rows={findingsQuery.data?.results ?? []}
          />
        </section>
        <section>
          <h2 className="text-lg font-medium mb-2">Evidence</h2>
          <EvidencePanel
            isLoading={evidenceQuery.isLoading}
            rows={evidenceQuery.data?.results ?? []}
          />
        </section>
      </div>
    </>
  );
}
