import { Link, useParams } from "react-router-dom";
import { PageHeader } from "../../components/PageHeader";
import { DetailPageGuard } from "../../components/DetailPageGuard";
import { MetaList, MetaRow } from "../../components/MetaList";
import { Table, type TableColumn } from "../../components/Table";
import { EmptyState } from "../../components/EmptyState";
import {
  ROUTES,
  scanRunDetailPath,
  stubDetailPath,
  targetResultPath,
} from "../../app/routes";
import { useFindingDetailQuery, useFindingEvidenceQuery } from "./api";
import type { Evidence, Finding } from "../../types/api";

const dash = (v: string | null) => v || "—";

const evidenceColumns: TableColumn<Evidence>[] = [
  { key: "source", header: "Source", cell: (e) => e.source },
  { key: "url", header: "URL", cell: (e) => dash(e.url) },
  { key: "field", header: "Field", cell: (e) => dash(e.field) },
  {
    key: "matched_value",
    header: "Matched value",
    cell: (e) => <code>{dash(e.matched_value)}</code>,
  },
  {
    key: "raw_excerpt",
    header: "Raw excerpt",
    cell: (e) => <code>{dash(e.raw_excerpt)}</code>,
  },
  {
    key: "created_at",
    header: "Created at",
    cell: (e) => e.created_at.slice(0, 19),
  },
];

function LinkedEvidence({ findingId }: { findingId: string }) {
  const query = useFindingEvidenceQuery(findingId);
  const rows = query.data?.results ?? [];
  return (
    <section data-testid="finding-evidence-section">
      <h2>Linked evidence ({query.data?.count ?? 0})</h2>
      <Table<Evidence>
        columns={evidenceColumns}
        rows={rows}
        rowKey={(e) => e.id}
        rowTestId={(e) => `finding-evidence-row-${e.id}`}
        isLoading={query.isLoading}
        emptyState={<EmptyState message="No linked evidence." />}
      />
    </section>
  );
}

function DetailBody({ finding }: { finding: Finding }) {
  return (
    <>
      <PageHeader title={finding.title} />
      <MetaList>
        <MetaRow label="Target">
          <Link to={targetResultPath(finding.target)}>
            <code>{finding.target}</code>
          </Link>
        </MetaRow>
        <MetaRow label="Scan run">
          <Link to={scanRunDetailPath(finding.scan_run)}>
            <code>{finding.scan_run}</code>
          </Link>
        </MetaRow>
        <MetaRow label="Stub">
          <Link to={stubDetailPath(finding.stub_slug)}>{finding.stub_slug}</Link>
        </MetaRow>
        <MetaRow label="Category">{finding.category}</MetaRow>
        <MetaRow label="Severity">{finding.severity}</MetaRow>
        <MetaRow label="Confidence">{finding.confidence || "—"}</MetaRow>
        <MetaRow label="Status">{finding.status}</MetaRow>
        <MetaRow label="Created at">{finding.created_at.slice(0, 19)}</MetaRow>
        <MetaRow label="Updated at">{finding.updated_at.slice(0, 19)}</MetaRow>
      </MetaList>
      <section data-testid="finding-data-section">
        <h2>Data</h2>
        <pre data-testid="finding-data-json">
          {JSON.stringify(finding.data, null, 2)}
        </pre>
      </section>
      <LinkedEvidence findingId={finding.id} />
    </>
  );
}

export function FindingDetail() {
  const { findingId } = useParams();
  const query = useFindingDetailQuery(findingId);
  return (
    <DetailPageGuard
      query={query}
      options={{
        notFoundTitle: "Finding not found",
        notFoundMessage: `No finding matches "${findingId}".`,
        backTo: ROUTES.findings,
        backLabel: "Back to findings.",
        errorTitle: "Finding",
        errorBody: "Could not load finding.",
      }}
    >
      {(finding) => <DetailBody finding={finding} />}
    </DetailPageGuard>
  );
}
