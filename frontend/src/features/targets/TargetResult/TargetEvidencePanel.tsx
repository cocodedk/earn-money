import { useTargetEvidenceQuery } from "../api";
import { dash, fmtDate } from "./format";
import { TargetSection } from "./TargetSection";
import type { Evidence } from "../../../types/api";

const columns = [
  { key: "source", header: "Source", cell: (e: Evidence) => e.source },
  { key: "scan_run", header: "Scan run", cell: (e: Evidence) => <code>{e.scan_run.slice(0, 8)}</code> },
  { key: "url", header: "URL", cell: (e: Evidence) => dash(e.url) },
  { key: "method", header: "Method", cell: (e: Evidence) => dash(e.method) },
  { key: "field", header: "Field", cell: (e: Evidence) => dash(e.field) },
  { key: "matched_value", header: "Matched value", cell: (e: Evidence) => <code>{dash(e.matched_value)}</code> },
  { key: "created_at", header: "Created at", cell: (e: Evidence) => fmtDate(e.created_at) },
];

export function TargetEvidencePanel({ targetId }: { targetId: string }) {
  return (
    <TargetSection<Evidence>
      query={useTargetEvidenceQuery(targetId)}
      columns={columns}
      rowTestIdPrefix="target-evidence-row-"
      copy={{
        slug: "target-evidence",
        heading: "Evidence for target",
        errorMessage: "Could not load evidence.",
        loadingMessage: "Loading evidence…",
        emptyMessage: "No evidence yet for this target.",
        truncationNoun: "evidence",
      }}
    />
  );
}
