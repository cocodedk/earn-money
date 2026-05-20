import { StatusBadge as GenericStatusBadge } from "../../components/StatusBadge";
import type { ScanRunStatus } from "../../types/api";

const STATUS_PALETTE: Record<ScanRunStatus, string> = {
  queued: "bg-gray-200 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  running: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-100",
  paused: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-100",
  stopping: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-100",
  stopped: "bg-gray-200 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  failed: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100",
  done: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100",
};

export function StatusBadge({ status }: { status: ScanRunStatus }) {
  return <GenericStatusBadge status={status} palette={STATUS_PALETTE} />;
}
