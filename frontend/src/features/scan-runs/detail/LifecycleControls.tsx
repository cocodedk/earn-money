import { Button } from "../../../components/Button";
import { useScanRunLifecycleMutation } from "../api";
import type { LifecycleAction, ScanRun, ScanRunStatus } from "../../../types/api";

const ENABLED_ACTIONS: Record<ScanRunStatus, LifecycleAction[]> = {
  queued: ["start"],
  running: ["pause", "stop"],
  paused: ["resume", "stop"],
  stopping: [],
  stopped: [],
  failed: [],
  done: [],
};

const LABELS: Record<LifecycleAction, string> = {
  start: "Start",
  pause: "Pause",
  resume: "Resume",
  stop: "Stop",
};

const ALL_ACTIONS: LifecycleAction[] = ["start", "pause", "resume", "stop"];

export type LifecycleControlsProps = { scanRun: ScanRun };

export function LifecycleControls({ scanRun }: LifecycleControlsProps) {
  const mutation = useScanRunLifecycleMutation(scanRun.id);
  const enabled = ENABLED_ACTIONS[scanRun.status];
  return (
    <div className="flex items-center gap-2" data-testid="lifecycle-controls">
      {ALL_ACTIONS.map((action) => (
        <Button
          key={action}
          variant={action === "stop" ? "danger" : "primary"}
          disabled={!enabled.includes(action) || mutation.isPending}
          onClick={() => void mutation.mutateAsync(action)}
        >
          {LABELS[action]}
        </Button>
      ))}
    </div>
  );
}
