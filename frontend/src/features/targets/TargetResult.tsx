import { useParams } from "react-router-dom";
import { ROUTES } from "../../app/routes";
import { PageHeader } from "../../components/PageHeader";
import { DetailPageGuard } from "../../components/DetailPageGuard";
import { MetaList, MetaRow } from "../../components/MetaList";
import { useProjectNameLookup } from "../projects/useProjectNameLookup";
import { useTargetQuery } from "./api";
import { StatusBadge } from "./StatusBadge";
import { TargetScanRunsTable } from "./TargetResult/TargetScanRunsTable";
import { TargetFindingsPanel } from "./TargetResult/TargetFindingsPanel";
import { TargetEvidencePanel } from "./TargetResult/TargetEvidencePanel";
import { TargetEventsTable } from "./TargetResult/TargetEventsTable";
import { TargetAuthEventsPanel } from "./TargetResult/TargetAuthEventsPanel";
import type { Target } from "../../types/api";

function DetailBody({ target }: { target: Target }) {
  const projectName = useProjectNameLookup();
  return (
    <>
      <PageHeader
        title={`Target · ${target.id.slice(0, 8)} · ${target.base_url}`}
      />
      <MetaList>
        <MetaRow label="ID">
          <code>{target.id}</code>
        </MetaRow>
        <MetaRow label="Project">{projectName(target.project)}</MetaRow>
        <MetaRow label="Base URL">{target.base_url}</MetaRow>
        <MetaRow label="Host">{target.host}</MetaRow>
        <MetaRow label="IP">{target.ip ?? "—"}</MetaRow>
        <MetaRow label="Status">
          <StatusBadge status={target.status} />
        </MetaRow>
        <MetaRow label="Created at">{target.created_at.slice(0, 19)}</MetaRow>
      </MetaList>
      <TargetScanRunsTable targetId={target.id} />
      <TargetFindingsPanel targetId={target.id} />
      <TargetEvidencePanel targetId={target.id} />
      <TargetAuthEventsPanel targetId={target.id} />
      <TargetEventsTable targetId={target.id} />
    </>
  );
}

export function TargetResult() {
  const { targetId } = useParams();
  const query = useTargetQuery(targetId);
  return (
    <DetailPageGuard
      query={query}
      options={{
        notFoundTitle: "Target not found",
        notFoundMessage: `No target matches "${targetId}".`,
        backTo: ROUTES.targets,
        backLabel: "Back to targets.",
        errorTitle: "Target",
        errorBody: "Could not load target.",
      }}
    >
      {(target) => <DetailBody target={target} />}
    </DetailPageGuard>
  );
}
