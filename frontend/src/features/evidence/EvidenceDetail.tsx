import { Link, useParams } from "react-router-dom";
import { PageHeader } from "../../components/PageHeader";
import { Callout } from "../../components/Callout";
import { useEvidenceDetailQuery } from "./api";

export function EvidenceDetail() {
  const id = useParams().id as string;
  const query = useEvidenceDetailQuery(id);

  if (query.isError) {
    return (
      <>
        <PageHeader title="Evidence" />
        <div className="mt-4">
          <Callout variant="error" title="Not found">
            This evidence row could not be loaded.
          </Callout>
        </div>
      </>
    );
  }

  const e = query.data;
  return (
    <>
      <PageHeader title="Evidence" />
      {e && (
        <div className="mt-4 grid grid-cols-[160px_1fr] gap-y-2 max-w-3xl text-sm">
          <div className="text-gray-600">Target</div>
          <div className="font-mono">
            <Link
              to={`/targets/${e.target}/results`}
              className="text-blue-700 hover:underline"
            >
              {e.target}
            </Link>
          </div>
          <div className="text-gray-600">Scan run</div>
          <div className="font-mono">
            <Link
              to={`/scan-runs/${e.scan_run}`}
              className="text-blue-700 hover:underline"
            >
              {e.scan_run}
            </Link>
          </div>
          <div className="text-gray-600">Finding</div>
          <div className="font-mono">
            {e.finding ? (
              <Link
                to={`/findings/${e.finding}`}
                className="text-blue-700 hover:underline"
              >
                {e.finding}
              </Link>
            ) : (
              <span className="text-gray-500">unlinked</span>
            )}
          </div>
          <div className="text-gray-600">Source</div>
          <div>{e.source}</div>
          <div className="text-gray-600">URL</div>
          <div className="font-mono break-all">{e.url ?? "—"}</div>
          <div className="text-gray-600">Method</div>
          <div>{e.method ?? "—"}</div>
          <div className="text-gray-600">Field</div>
          <div>{e.field ?? "—"}</div>
          <div className="text-gray-600">Matched value</div>
          <div className="font-mono break-all">{e.matched_value ?? "—"}</div>
          <div className="text-gray-600">Raw excerpt</div>
          <div>
            {e.raw_excerpt ? (
              <pre className="whitespace-pre-wrap font-mono text-xs bg-gray-50 border border-gray-200 rounded p-3 max-h-72 overflow-auto">
                {e.raw_excerpt}
              </pre>
            ) : (
              "—"
            )}
          </div>
          <div className="text-gray-600">Content hash</div>
          <div className="font-mono">{e.content_hash}</div>
          <div className="text-gray-600">Created</div>
          <div>{e.created_at}</div>
          <div className="col-span-2 mt-2">
            <div className="text-gray-600 text-sm mb-1">Data</div>
            <pre className="whitespace-pre-wrap font-mono text-xs bg-gray-50 border border-gray-200 rounded p-3 max-h-72 overflow-auto">
              {JSON.stringify(e.data, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </>
  );
}
