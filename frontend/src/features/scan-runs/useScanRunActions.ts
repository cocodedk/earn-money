import {
  usePauseScanRunMutation,
  useResumeScanRunMutation,
  useStartScanRunMutation,
  useStopScanRunMutation,
} from "./api";
import type { LifecycleAction, ScanRun, ScanRunStatus } from "../../types/api";

export const VALID_ACTIONS: Record<ScanRunStatus, readonly LifecycleAction[]> = {
  queued: ["start"],
  running: ["pause", "stop"],
  paused: ["resume", "stop"],
  stopping: [],
  stopped: [],
  failed: [],
  done: [],
};

export const ACTION_LABEL: Record<LifecycleAction, string> = {
  start: "Start",
  pause: "Pause",
  resume: "Resume",
  stop: "Stop",
};

export type ScanRunActions = {
  visibleActions: readonly LifecycleAction[];
  handlers: Record<LifecycleAction, () => void>;
  isPending: boolean;
};

export function useScanRunActions(run: ScanRun): ScanRunActions {
  const start = useStartScanRunMutation();
  const pause = usePauseScanRunMutation();
  const resume = useResumeScanRunMutation();
  const stop = useStopScanRunMutation();
  return {
    visibleActions: VALID_ACTIONS[run.status],
    handlers: {
      start: () => start.mutate(run.id),
      pause: () => pause.mutate(run.id),
      resume: () => resume.mutate(run.id),
      stop: () => stop.mutate(run.id),
    },
    isPending:
      start.isPending || pause.isPending || resume.isPending || stop.isPending,
  };
}
