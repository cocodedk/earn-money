import { useState } from "react";
import type { AgentNote, AgentTurn } from "./types";
import styles from "./DiscoveryChips.module.css";

type Chip = { icon: string; label: string; kind: string };

const CHIP_CONFIG: Record<string, { icon: string; kind: string }> = {
  route: { icon: "🔗", kind: "route" },
  candidate: { icon: "🎯", kind: "candidate" },
  parameter: { icon: "📝", kind: "parameter" },
  gap: { icon: "❓", kind: "gap" },
};

const MAX_VISIBLE = 3;

function chipsFromNotes(notes: AgentNote[]): Chip[] {
  const chips: Chip[] = [];
  for (const note of notes) {
    const cfg = CHIP_CONFIG[note.note_type];
    if (!cfg) continue;
    const text = typeof note.content === "object" && note.content !== null
      ? (note.content as Record<string, unknown>).text
      : note.content;
    const label = typeof text === "string" ? text : JSON.stringify(note.content);
    chips.push({ icon: cfg.icon, label, kind: cfg.kind });
  }
  return chips;
}

function chipsFromObservations(turn: AgentTurn): Chip[] {
  const chips: Chip[] = [];
  for (const action of turn.actions) {
    for (const obs of action.observations) {
      const disc = obs.data.discovered as Record<string, unknown[]> | undefined;
      if (!disc) continue;
      const routes = Array.isArray(disc.routes) ? disc.routes : [];
      for (const r of routes) {
        chips.push({ icon: "🔗", label: String(r), kind: "route" });
      }
      const assets = Array.isArray(disc.assets) ? disc.assets : [];
      for (const a of assets) {
        chips.push({ icon: "🎯", label: String(a), kind: "candidate" });
      }
    }
  }
  return chips;
}

function dedup(chips: Chip[]): Chip[] {
  const seen = new Set<string>();
  return chips.filter((c) => {
    const key = `${c.kind}:${c.label}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

type Props = { turn: AgentTurn; notes: AgentNote[] };

export function DiscoveryChips({ turn, notes }: Props) {
  const [expanded, setExpanded] = useState(false);
  const all = dedup([...chipsFromNotes(notes), ...chipsFromObservations(turn)]);
  if (all.length === 0) return null;

  const visible = expanded ? all : all.slice(0, MAX_VISIBLE);
  const remaining = all.length - MAX_VISIBLE;

  return (
    <div className={styles.chips} data-testid="discovery-chips">
      {visible.map((chip, i) => (
        <span key={i} className={styles.chip} data-kind={chip.kind}>
          <span className={styles.chipIcon}>{chip.icon}</span>
          {chip.label}
        </span>
      ))}
      {!expanded && remaining > 0 && (
        <button
          type="button"
          className={styles.more}
          onClick={() => setExpanded(true)}
          data-testid="chips-expand"
        >
          +{remaining} more
        </button>
      )}
    </div>
  );
}
