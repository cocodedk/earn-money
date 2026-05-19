import { Link, useParams } from "react-router-dom";
import { PageHeader } from "../../components/PageHeader";
import { Callout } from "../../components/Callout";
import { StatusBadge } from "../../components/StatusBadge";
import { FindingsPanel } from "../scan-runs/detail/FindingsPanel";
import { EvidencePanel } from "../scan-runs/detail/EvidencePanel";
import { Table, type TableColumn } from "../../components/Table";
import { EmptyState } from "../../components/EmptyState";
import { useTargetDetailQuery } from "./api";
import { useFindingsQuery } from "../findings/api";
import { useEvidenceQuery } from "../evidence/api";
import { useScanRunsQuery } from "../scan-runs/api";
import type { ScanRun } from "../../types/api";

const scanRunColumns: TableColumn<ScanRun>[] = [
  {
    key: "id",
    header: "ID",
    cell: (r) => (
      <Link
        to={`/scan-runs/${r.id}`}
        className="font-mono text-blue-700 hover:underline"
      >
        {r.id.slice(0, 8)}
      </Link>
    ),
  },
  { key: "stub_slug", header: "Stub", cell: (r) => r.stub_slug },
  {
    key: "status",
    header: "Status",
    cell: (r) => <StatusBadge status={r.status} />,
  },
  { key: "findings_count", header: "Findings", cell: (r) => r.findings_count },
  {
    key: "started_at",
    header: "Started",
    cell: (r) => (r.started_at ? r.started_at.slice(0, 19).replace("T", " ") : "—"),
  },
];

export function TargetResult() {
  const id = useParams().id as string;
  const targetQuery = useTargetDetailQuery(id);
  const findingsQuery = useFindingsQuery({ target: id });
  const evidenceQuery = useEvidenceQuery({ target: id });
  // Scan runs aren't filterable by target server-side yet; the operator can
  // open scan-run rows via the Findings/Evidence panels' embedded links.
  // For the standalone "Latest scan runs for target" section, we surface the
  // global scan-runs list scoped by the target's project — slice 4 can tighten
  // this once a per-target filter lands.
  const scanRunsQuery = useScanRunsQuery(
    targetQuery.data ? { project: targetQuery.data.project } : {},
  );

  if (targetQuery.isError) {
    return (
      <>
        <PageHeader title="Target" />
        <div className="mt-4">
          <Callout variant="error" title="Not found">
            This target could not be loaded.
          </Callout>
        </div>
      </>
    );
  }

  const t = targetQuery.data;
  return (
    <>
      <PageHeader title={t?.base_url ?? "Target"} />
      {t && (
        <div className="mt-4 flex flex-col gap-6">
          <dl
            data-testid="target-summary"
            className="grid grid-cols-[160px_1fr] gap-y-1 max-w-2xl text-sm"
          >
            <dt className="text-gray-600">Base URL</dt>
            <dd className="font-mono">{t.base_url}</dd>
            <dt className="text-gray-600">Host</dt>
            <dd className="font-mono">{t.host ?? "—"}</dd>
            <dt className="text-gray-600">IP</dt>
            <dd className="font-mono">{t.ip ?? "—"}</dd>
            <dt className="text-gray-600">Status</dt>
            <dd>
              <StatusBadge status={t.status} />
            </dd>
            <dt className="text-gray-600">Created</dt>
            <dd>{t.created_at}</dd>
          </dl>
          <section>
            <h2 className="text-lg font-medium mb-2">
              Latest scan runs for target
            </h2>
            <Table<ScanRun>
              columns={scanRunColumns}
              rows={scanRunsQuery.data?.results ?? []}
              rowKey={(r) => r.id}
              isLoading={scanRunsQuery.isLoading}
              emptyState={<EmptyState message="No scan runs yet." />}
            />
          </section>
          <section>
            <h2 className="text-lg font-medium mb-2">Findings for target</h2>
            <FindingsPanel
              isLoading={findingsQuery.isLoading}
              rows={findingsQuery.data?.results ?? []}
            />
          </section>
          <section>
            <h2 className="text-lg font-medium mb-2">Evidence for target</h2>
            <EvidencePanel
              isLoading={evidenceQuery.isLoading}
              rows={evidenceQuery.data?.results ?? []}
            />
          </section>
        </div>
      )}
    </>
  );
}
