import { useParams } from "react-router-dom";
import { PageHeader } from "../../components/PageHeader";
import { Callout } from "../../components/Callout";
import { useStubDetailQuery } from "./api";

export function StubDetail() {
  const { slug = null } = useParams();
  const query = useStubDetailQuery(slug);

  if (query.isError) {
    return (
      <>
        <PageHeader title={`Stub ${slug ?? ""}`} />
        <div className="mt-4">
          <Callout variant="error" title="Not found">
            This stub could not be loaded.
          </Callout>
        </div>
      </>
    );
  }

  const stub = query.data;
  return (
    <>
      <PageHeader title={stub?.title ?? `Stub ${slug ?? ""}`} />
      {stub && (
        <div className="mt-4 grid grid-cols-[160px_1fr] gap-y-2 max-w-3xl text-sm">
          <div className="text-gray-600">Slug</div>
          <div className="font-mono">{stub.slug}</div>
          <div className="text-gray-600">Phase</div>
          <div>{stub.phase_title}</div>
          <div className="text-gray-600">Category</div>
          <div>{stub.category}</div>
          <div className="text-gray-600">Fixture</div>
          <div>{stub.fixture ?? "—"}</div>
          <div className="text-gray-600">Path</div>
          <div className="font-mono">{stub.path}</div>
          <div className="col-span-2 mt-4">
            <pre className="whitespace-pre-wrap font-mono text-xs bg-gray-50 border border-gray-200 rounded p-3 max-h-96 overflow-auto">
              {stub.body}
            </pre>
          </div>
        </div>
      )}
    </>
  );
}
