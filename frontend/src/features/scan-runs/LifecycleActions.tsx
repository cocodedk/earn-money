import { ACTION_LABEL, useScanRunActions } from "./useScanRunActions";
import type { ScanRun } from "../../types/api";

export function LifecycleActions({ run }: { run: ScanRun }) {
  const { visibleActions, handlers } = useScanRunActions(run);
  if (visibleActions.length === 0) return null;
  return (
    <div className="flex gap-2">
      {visibleActions.map((action) => (
        <button
          key={action}
          type="button"
          onClick={handlers[action]}
          className="rounded bg-gray-200 px-3 py-1 text-sm hover:bg-gray-300"
        >
          {ACTION_LABEL[action]}
        </button>
      ))}
    </div>
  );
}
