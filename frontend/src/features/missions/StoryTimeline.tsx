import { useEffect, useRef, useState } from "react";
import type { UIEvent } from "react";
import type { AgentNote, AgentTurn } from "./types";
import { TurnCard } from "./TurnCard";
import { DiscoveryChips } from "./DiscoveryChips";
import styles from "./StoryTimeline.module.css";

type Props = {
  turns: AgentTurn[];
  notes: AgentNote[];
  isLive: boolean;
  isTruncated: boolean;
  isNotesTruncated: boolean;
};

const NOTE_ICONS: Record<string, string> = {
  hypothesis: "💡", gap: "❓", credential_label: "🔑",
  route: "🔗", parameter: "📝", candidate: "🎯",
};

const SCROLL_THRESHOLD_PX = 20;

function noteText(note: AgentNote): string {
  if (typeof note.content === "object" && note.content !== null) {
    const text = (note.content as Record<string, unknown>).text;
    return typeof text === "string" ? text : JSON.stringify(note.content);
  }
  return String(note.content);
}

function groupNotesByTurn(notes: AgentNote[]): Map<number, AgentNote[]> {
  const map = new Map<number, AgentNote[]>();
  for (const note of notes) {
    const list = map.get(note.turn_index) ?? [];
    list.push(note);
    map.set(note.turn_index, list);
  }
  return map;
}

function orderTurns(turns: AgentTurn[]): AgentTurn[] {
  return [...turns].sort((a, b) => a.index - b.index);
}

function isScrolledUp(el: HTMLElement): boolean {
  return el.scrollTop < el.scrollHeight - el.clientHeight - SCROLL_THRESHOLD_PX;
}

export function StoryTimeline({
  turns, notes, isLive, isTruncated, isNotesTruncated,
}: Props) {
  const orderedTurns = orderTurns(turns);
  const notesByTurn = groupNotesByTurn(notes);
  const [autoScroll, setAutoScroll] = useState(true);
  const lastRef = useRef<HTMLDivElement | null>(null);
  const prevLenRef = useRef(orderedTurns.length);

  useEffect(() => {
    const prev = prevLenRef.current;
    prevLenRef.current = orderedTurns.length;
    if (autoScroll && orderedTurns.length > prev && lastRef.current) {
      lastRef.current.scrollIntoView({ block: "end" });
    }
  }, [orderedTurns.length, autoScroll]);

  function onScroll(e: UIEvent<HTMLDivElement>) {
    setAutoScroll(!isScrolledUp(e.currentTarget));
  }

  if (orderedTurns.length === 0) {
    return <p className={styles.empty}>The agent has not started yet.</p>;
  }

  return (
    <div
      onScroll={onScroll}
      aria-label={isLive ? "Live mission timeline" : "Mission timeline"}
      className={styles.timeline}
    >
      {isTruncated && (
        <p className={styles.truncHint}>Showing first {orderedTurns.length} turns</p>
      )}
      {orderedTurns.map((turn, i) => {
        const turnNotes = notesByTurn.get(turn.index) ?? [];
        return (
          <div key={turn.id} ref={i === orderedTurns.length - 1 ? lastRef : undefined}>
            <TurnCard turn={turn} />
            <DiscoveryChips turn={turn} notes={turnNotes} />
            {turnNotes.map((note) => (
              <div key={note.id} data-testid={`note-${note.id}`} className={styles.note}>
                <span className={styles.noteIcon}>{NOTE_ICONS[note.note_type] ?? "📌"}</span>
                <span className={styles.noteType}>{note.note_type}</span>
                {noteText(note)}
              </div>
            ))}
          </div>
        );
      })}
      {isNotesTruncated && (
        <p className={styles.truncHint}>Some notebook entries are hidden</p>
      )}
    </div>
  );
}
