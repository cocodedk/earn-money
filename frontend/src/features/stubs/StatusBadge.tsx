import { StatusBadge as GenericStatusBadge } from "../../components/StatusBadge";
import type { StubStatus } from "../../types/api";

const STATUS_PALETTE: Record<StubStatus, string> = {
  done: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100",
  "in-progress": "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-100",
  blocked: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-100",
  pending: "bg-gray-200 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
};

export function StatusBadge({ status }: { status: StubStatus }) {
  return <GenericStatusBadge status={status} palette={STATUS_PALETTE} />;
}
