import { Link, useParams } from "react-router-dom";
import { PageHeader } from "../../components/PageHeader";
import { Callout } from "../../components/Callout";
import { SeverityBadge } from "../../components/SeverityBadge";
import { Table, type TableColumn } from "../../components/Table";
import { EmptyState } from "../../components/EmptyState";
import { useFindingDetailQuery } from "./api";
import { useEvidenceQuery } from "../evidence/api";
import type { Evidence } from "../../types/api";

const evidenceColumns: TableColumn<Evidence>[] = [
  { key: "source", header: "Source", cell: (r) => r.source },
  { key: "url", header: "URL", cell: (r) => r.url ?? "—" },
  { key: "field", header: "Field", cell: (r) => r.field ?? "—" },
  {
    key: "matched_value",
    header: "Matched value",
    cell: (r) => (
      <span className="font-mono text-xs">{r.matched_value ?? "—"}</span>
    ),
  },
  {
    key: "created_at",
    header: "Created",
    cell: (r) => r.created_at.slice(0, 10),
  },
];

export function FindingDetail() {
  const id = useParams().id as string;
  const findingQuery = useFindingDetailQuery(id);
  const evidenceQuery = useEvidenceQuery({ finding: id });

  if (findingQuery.isError) {
    return (
      <>
        <PageHeader title="Finding" />
        <div className="mt-4">
          <Callout variant="error" title="Not found">
            This finding could not be loaded.
          </Callout>
        </div>
      </>
    );
  }

  const f = findingQuery.data;
  return (
    <>
      <PageHeader title={f?.title ?? "Finding"} />
      {f && (
        <div className="mt-4 grid grid-cols-[160px_1fr] gap-y-2 max-w-3xl text-sm">
          <div className="text-gray-600">Target</div>
          <div className="font-mono">
            <Link
              to={`/targets/${f.target}/results`}
              className="text-blue-700 hover:underline"
            >
              {f.target}
            </Link>
          </div>
          <div className="text-gray-600">Scan run</div>
          <div className="font-mono">
            <Link
              to={`/scan-runs/${f.scan_run}`}
              className="text-blue-700 hover:underline"
            >
              {f.scan_run}
            </Link>
          </div>
          <div className="text-gray-600">Stub</div>
          <div>{f.stub_slug}</div>
          <div className="text-gray-600">Category</div>
          <div>{f.category}</div>
          <div className="text-gray-600">Severity</div>
          <div>
            <SeverityBadge severity={f.severity} />
          </div>
          <div className="text-gray-600">Confidence</div>
          <div>{f.confidence}</div>
          <div className="text-gray-600">Status</div>
          <div>{f.status}</div>
          <div className="text-gray-600">Created</div>
          <div>{f.created_at}</div>
          <div className="text-gray-600">Updated</div>
          <div>{f.updated_at}</div>
          <div className="col-span-2 mt-2">
            <div className="text-gray-600 text-sm mb-1">Data</div>
            <pre className="whitespace-pre-wrap font-mono text-xs bg-gray-50 border border-gray-200 rounded p-3 max-h-72 overflow-auto">
              {JSON.stringify(f.data, null, 2)}
            </pre>
          </div>
          <div className="col-span-2 mt-4">
            <h2 className="text-lg font-medium mb-2">Linked evidence</h2>
            <Table<Evidence>
              columns={evidenceColumns}
              rows={evidenceQuery.data?.results ?? []}
              rowKey={(r) => r.id}
              isLoading={evidenceQuery.isLoading}
              emptyState={<EmptyState message="No linked evidence." />}
            />
          </div>
        </div>
      )}
    </>
  );
}
