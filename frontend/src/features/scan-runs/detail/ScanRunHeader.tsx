import { StatusBadge } from "../../../components/StatusBadge";
import type { ScanRun } from "../../../types/api";

export type ScanRunHeaderProps = { scanRun: ScanRun };

function formatTimestamp(value: string | null): string {
  if (!value) return "—";
  return value.slice(0, 19).replace("T", " ");
}

export function ScanRunHeader({ scanRun }: ScanRunHeaderProps) {
  return (
    <dl
      data-testid="scan-run-header"
      className="grid grid-cols-[160px_1fr] gap-y-1 max-w-2xl text-sm"
    >
      <dt className="text-gray-600">Scan run ID</dt>
      <dd className="font-mono">{scanRun.id}</dd>
      <dt className="text-gray-600">Project</dt>
      <dd className="font-mono">{scanRun.project}</dd>
      <dt className="text-gray-600">Stub</dt>
      <dd>{scanRun.stub_slug}</dd>
      <dt className="text-gray-600">Status</dt>
      <dd>
        <StatusBadge status={scanRun.status} />
      </dd>
      <dt className="text-gray-600">Started at</dt>
      <dd>{formatTimestamp(scanRun.started_at)}</dd>
      <dt className="text-gray-600">Finished at</dt>
      <dd>{formatTimestamp(scanRun.finished_at)}</dd>
    </dl>
  );
}
