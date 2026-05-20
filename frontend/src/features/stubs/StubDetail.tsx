import { useParams } from "react-router-dom";
import { ROUTES } from "../../app/routes";
import { PageHeader } from "../../components/PageHeader";
import { DetailPageGuard } from "../../components/DetailPageGuard";
import { MetaList, MetaRow } from "../../components/MetaList";
import { useStubQuery } from "./api";
import { StatusBadge } from "./StatusBadge";
import type { Stub } from "../../types/api";

function StubBody({ stub }: { stub: Stub }) {
  return (
    <>
      <PageHeader title={`${stub.slug} · ${stub.title}`} />
      <MetaList>
        <MetaRow label="Phase">{stub.phase_title}</MetaRow>
        <MetaRow label="Category">{stub.category || "—"}</MetaRow>
        <MetaRow label="Spec slug">{stub.spec_slug || "—"}</MetaRow>
        <MetaRow label="Status">
          <StatusBadge status={stub.status} />
        </MetaRow>
        <MetaRow label="Fixture">{stub.fixture}</MetaRow>
        <MetaRow label="Path">
          <code>{stub.path}</code>
        </MetaRow>
      </MetaList>
      <pre
        role="article"
        className="mt-6 whitespace-pre-wrap font-mono text-sm bg-gray-50 p-4 rounded border border-gray-200"
      >
        {stub.body}
      </pre>
    </>
  );
}

export function StubDetail() {
  const { slug } = useParams();
  const query = useStubQuery(slug);
  return (
    <DetailPageGuard
      query={query}
      options={{
        notFoundTitle: "Stub not found",
        notFoundMessage: `No stub matches "${slug}".`,
        backTo: ROUTES.stubs,
        backLabel: "Back to stubs.",
        errorTitle: "Stub",
        errorBody: "Could not load stub.",
      }}
    >
      {(stub) => <StubBody stub={stub} />}
    </DetailPageGuard>
  );
}
