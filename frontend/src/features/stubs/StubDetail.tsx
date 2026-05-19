import { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { ROUTES } from "../../app/routes";
import { PageHeader } from "../../components/PageHeader";
import { Callout } from "../../components/Callout";
import { isHttpStatus } from "../../lib/http";
import { useStubQuery } from "./api";
import { StatusBadge } from "./StatusBadge";
import { BACKEND_UNREACHABLE } from "../../lib/applyParsedError";
import type { Stub } from "../../types/api";

function MetaRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex gap-4 text-sm">
      <span className="w-32 font-medium text-gray-600">{label}</span>
      <span>{children}</span>
    </div>
  );
}

function StubBody({ stub }: { stub: Stub }) {
  return (
    <>
      <PageHeader title={`${stub.slug} · ${stub.title}`} />
      <div className="mt-4 flex flex-col gap-2">
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
      </div>
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

  if (isHttpStatus(query.error, 404)) {
    return (
      <>
        <PageHeader title="Stub not found" />
        <div className="mt-4">
          <Callout variant="info">
            No stub matches "{slug}".{" "}
            <Link to={ROUTES.stubs}>Back to stubs.</Link>
          </Callout>
        </div>
      </>
    );
  }
  if (query.isError) {
    return (
      <>
        <PageHeader title="Stub" />
        <div className="mt-4">
          <Callout variant="error" title={BACKEND_UNREACHABLE}>
            Could not load stub.
          </Callout>
        </div>
      </>
    );
  }
  if (!query.data) {
    return <PageHeader title="Loading…" />;
  }
  return <StubBody stub={query.data} />;
}
