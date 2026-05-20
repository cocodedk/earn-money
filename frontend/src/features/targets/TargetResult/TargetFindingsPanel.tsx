import { useTargetFindingsQuery } from "../api";
import { fmtDate } from "./format";
import { TargetSection } from "./TargetSection";
import type { Finding } from "../../../types/api";

const columns = [
  { key: "title", header: "Title", cell: (f: Finding) => f.title },
  { key: "scan_run", header: "Scan run", cell: (f: Finding) => <code>{f.scan_run.slice(0, 8)}</code> },
  { key: "category", header: "Category", cell: (f: Finding) => f.category },
  { key: "severity", header: "Severity", cell: (f: Finding) => f.severity },
  { key: "confidence", header: "Confidence", cell: (f: Finding) => f.confidence || "—" },
  { key: "status", header: "Status", cell: (f: Finding) => f.status },
  { key: "created_at", header: "Created at", cell: (f: Finding) => fmtDate(f.created_at) },
];

export function TargetFindingsPanel({ targetId }: { targetId: string }) {
  return (
    <TargetSection<Finding>
      query={useTargetFindingsQuery(targetId)}
      columns={columns}
      rowTestIdPrefix="target-finding-row-"
      copy={{
        slug: "target-findings",
        heading: "Findings for target",
        errorMessage: "Could not load findings.",
        loadingMessage: "Loading findings…",
        emptyMessage: "No findings yet for this target.",
        truncationNoun: "findings",
      }}
    />
  );
}
