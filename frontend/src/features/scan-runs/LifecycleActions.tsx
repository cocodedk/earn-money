import { ACTION_LABEL, useScanRunActions } from "./useScanRunActions";
import type { ScanRun } from "../../types/api";
import styles from "./LifecycleActions.module.css";

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
          className={styles.button}
        >
          {ACTION_LABEL[action]}
        </button>
      ))}
    </div>
  );
}
