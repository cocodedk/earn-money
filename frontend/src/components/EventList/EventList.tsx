import { useEffect, useRef, useState } from "react";
import styles from "./EventList.module.css";
import type { ScanEvent, ScanEventLevel } from "../../types/api";

export type EventListProps = { events: ScanEvent[] };

const levelOrder: Record<ScanEventLevel, number> = {
  debug: 0,
  info: 1,
  warning: 2,
  error: 3,
};

const levelOptions: { value: ScanEventLevel | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "debug", label: "Debug" },
  { value: "info", label: "Info" },
  { value: "warning", label: "Warning" },
  { value: "error", label: "Error" },
];

export function EventList({ events }: EventListProps) {
  const [minLevel, setMinLevel] = useState<ScanEventLevel | "all">("all");
  const [autoScroll, setAutoScroll] = useState(true);
  const scrollerRef = useRef<HTMLDivElement | null>(null);

  const visible =
    minLevel === "all"
      ? events
      : events.filter((e) => levelOrder[e.level] >= levelOrder[minLevel]);

  useEffect(() => {
    if (autoScroll && scrollerRef.current) {
      scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight;
    }
  }, [autoScroll, visible.length]);

  return (
    <div className={styles.panel}>
      <div className={styles.controls}>
        <label className={styles.filter}>
          Level
          <select
            value={minLevel}
            onChange={(e) =>
              setMinLevel(e.target.value as ScanEventLevel | "all")
            }
          >
            {levelOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <label className={styles.toggle}>
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
          />
          Auto-scroll
        </label>
      </div>
      <div className={styles.scroller} ref={scrollerRef}>
        {visible.length === 0 ? (
          <p className={styles.empty}>No events yet.</p>
        ) : (
          <ul className={styles.list}>
            {visible.map((e) => (
              <li
                key={e.id}
                data-testid="event-row"
                data-level={e.level}
                className={styles.row}
              >
                <span className={styles.time}>{e.created_at.slice(11, 19)}</span>
                <span className={styles.level}>{e.level}</span>
                <span className={styles.type}>{e.event_type}</span>
                <span className={styles.message}>{e.message}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
