import { StatusBadge as GenericStatusBadge } from "../../components/StatusBadge";
import type { TargetStatus } from "../../types/api";

const STATUS_PALETTE: Record<TargetStatus, string> = {
  active: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100",
  retired: "bg-gray-200 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
};

export function StatusBadge({ status }: { status: TargetStatus }) {
  return <GenericStatusBadge status={status} palette={STATUS_PALETTE} />;
}
