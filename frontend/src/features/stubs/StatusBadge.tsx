import type { StubStatus } from "../../types/api";

const STATUS_PALETTE: Record<StubStatus, string> = {
  done: "bg-green-100 text-green-800",
  "in-progress": "bg-blue-100 text-blue-800",
  blocked: "bg-amber-100 text-amber-800",
  pending: "bg-gray-200 text-gray-700",
};

export function StatusBadge({ status }: { status: StubStatus }) {
  return (
    <span
      data-testid={`status-${status}`}
      className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${STATUS_PALETTE[status]}`}
    >
      {status}
    </span>
  );
}
