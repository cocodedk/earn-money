import { Link, useParams } from "react-router-dom";
import { PageHeader } from "../../components/PageHeader";
import { DetailPageGuard } from "../../components/DetailPageGuard";
import { MetaList, MetaRow } from "../../components/MetaList";
import {
  ROUTES,
  findingDetailPath,
  scanRunDetailPath,
  targetResultPath,
} from "../../app/routes";
import { useEvidenceDetailQuery } from "./api";
import type { Evidence } from "../../types/api";

const dash = (v: string | null) => v || "—";

function DetailBody({ evidence }: { evidence: Evidence }) {
  return (
    <>
      <PageHeader title="Evidence" />
      <MetaList>
        <MetaRow label="Target">
          <Link to={targetResultPath(evidence.target)}>
            <code>{evidence.target}</code>
          </Link>
        </MetaRow>
        <MetaRow label="Scan run">
          <Link to={scanRunDetailPath(evidence.scan_run)}>
            <code>{evidence.scan_run}</code>
          </Link>
        </MetaRow>
        <MetaRow label="Finding">
          {evidence.finding ? (
            <Link
              to={findingDetailPath(evidence.finding)}
              data-testid="evidence-detail-finding-link"
            >
              <code>{evidence.finding}</code>
            </Link>
          ) : (
            "—"
          )}
        </MetaRow>
        <MetaRow label="Source">{evidence.source}</MetaRow>
        <MetaRow label="URL">{dash(evidence.url)}</MetaRow>
        <MetaRow label="Method">{dash(evidence.method)}</MetaRow>
        <MetaRow label="Field">{dash(evidence.field)}</MetaRow>
        <MetaRow label="Matched value">
          <code>{dash(evidence.matched_value)}</code>
        </MetaRow>
        <MetaRow label="Content hash">
          <code>{evidence.content_hash}</code>
        </MetaRow>
        <MetaRow label="Created at">
          {evidence.created_at.slice(0, 19)}
        </MetaRow>
      </MetaList>
      <section data-testid="evidence-raw-excerpt-section">
        <h2>Raw excerpt</h2>
        <pre data-testid="evidence-raw-excerpt">
          {dash(evidence.raw_excerpt)}
        </pre>
      </section>
      <section data-testid="evidence-data-section">
        <h2>Data</h2>
        <pre data-testid="evidence-data-json">
          {JSON.stringify(evidence.data, null, 2)}
        </pre>
      </section>
    </>
  );
}

export function EvidenceDetail() {
  const { evidenceId } = useParams();
  const query = useEvidenceDetailQuery(evidenceId);
  return (
    <DetailPageGuard
      query={query}
      options={{
        notFoundTitle: "Evidence not found",
        notFoundMessage: `No evidence matches "${evidenceId}".`,
        backTo: ROUTES.evidence,
        backLabel: "Back to evidence.",
        errorTitle: "Evidence",
        errorBody: "Could not load evidence.",
      }}
    >
      {(evidence) => <DetailBody evidence={evidence} />}
    </DetailPageGuard>
  );
}
