import { StatusBadge as GenericStatusBadge } from "../../components/StatusBadge";
import type { StubStatus } from "../../types/api";

const STATUS_PALETTE: Record<StubStatus, string> = {
  done: "bg-green-100 text-green-800",
  "in-progress": "bg-blue-100 text-blue-800",
  blocked: "bg-amber-100 text-amber-800",
  pending: "bg-gray-200 text-gray-700",
};

export function StatusBadge({ status }: { status: StubStatus }) {
  return <GenericStatusBadge status={status} palette={STATUS_PALETTE} />;
}
