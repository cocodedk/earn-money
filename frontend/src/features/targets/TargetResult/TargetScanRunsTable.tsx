import { Link } from "react-router-dom";
import { scanRunDetailPath } from "../../../app/routes";
import { useTargetScanRunsQuery } from "../api";
import { fmtDateTime } from "./format";
import { TargetSection } from "./TargetSection";
import type { ScanRun } from "../../../types/api";

const columns = [
  { key: "id", header: "ID", cell: (r: ScanRun) => <code>{r.id.slice(0, 8)}</code> },
  { key: "status", header: "Status", cell: (r: ScanRun) => r.status },
  { key: "started_at", header: "Started at", cell: (r: ScanRun) => fmtDateTime(r.started_at) },
  { key: "finished_at", header: "Finished at", cell: (r: ScanRun) => fmtDateTime(r.finished_at) },
  { key: "findings", header: "Findings", cell: (r: ScanRun) => r.findings_count },
  {
    key: "actions",
    header: "Actions",
    cell: (r: ScanRun) => <Link to={scanRunDetailPath(r.id)}>Open</Link>,
  },
];

export function TargetScanRunsTable({ targetId }: { targetId: string }) {
  return (
    <TargetSection<ScanRun>
      query={useTargetScanRunsQuery(targetId)}
      columns={columns}
      rowTestIdPrefix="target-scan-run-row-"
      copy={{
        slug: "target-scan-runs",
        heading: "Latest scan runs for target",
        errorMessage: "Could not load scan runs.",
        loadingMessage: "Loading scan runs…",
        emptyMessage: "No scan runs yet for this target.",
        truncationNoun: "scan runs",
      }}
    />
  );
}
