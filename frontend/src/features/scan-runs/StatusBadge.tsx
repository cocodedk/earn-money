import { StatusBadge as GenericStatusBadge } from "../../components/StatusBadge";
import type { ScanRunStatus } from "../../types/api";

const STATUS_PALETTE: Record<ScanRunStatus, string> = {
  queued: "bg-gray-200 text-gray-700",
  running: "bg-blue-100 text-blue-800",
  paused: "bg-yellow-100 text-yellow-800",
  stopping: "bg-orange-100 text-orange-800",
  stopped: "bg-gray-200 text-gray-700",
  failed: "bg-red-100 text-red-800",
  done: "bg-green-100 text-green-800",
};

export function StatusBadge({ status }: { status: ScanRunStatus }) {
  return <GenericStatusBadge status={status} palette={STATUS_PALETTE} />;
}
