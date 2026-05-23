# Mission Viewer Plan — Task 6: StoryTimeline Component

**Goal:** Scrolling list of TurnCards with inline notebook entries and auto-scroll.

---

### Task 8: StoryTimeline

**Files:**
- Create: `frontend/src/features/missions/StoryTimeline.tsx`
- Create: `frontend/src/features/missions/StoryTimeline.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/features/missions/StoryTimeline.test.tsx`:

```typescript
import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test/renderWithProviders";
import { StoryTimeline } from "./StoryTimeline";
import { makeTurn, makeNote, makeAction } from "./__fixtures__/mission";
import type { AgentTurn, AgentNote } from "./types";

function renderTimeline(
  turns: AgentTurn[] = [],
  notes: AgentNote[] = [],
  opts: { isTruncated?: boolean; isNotesTruncated?: boolean } = {},
) {
  return renderWithProviders(
    <StoryTimeline
      turns={turns}
      notes={notes}
      isLive={false}
      isTruncated={opts.isTruncated ?? false}
      isNotesTruncated={opts.isNotesTruncated ?? false}
    />,
  );
}

describe("StoryTimeline", () => {
  it("shows empty state when no turns", () => {
    renderTimeline();
    expect(screen.getByText("The agent has not started yet.")).toBeInTheDocument();
  });

  it("renders turns in ascending order", () => {
    const turns = [
      makeTurn({ index: 0, actions: [makeAction({ goal: "First" })] }),
      makeTurn({ index: 1, id: "t-2", actions: [makeAction({ goal: "Second", id: "a-2" })] }),
    ];
    renderTimeline(turns);
    const cards = screen.getAllByTestId(/^turn-card-/);
    expect(cards).toHaveLength(2);
    expect(cards[0]).toHaveAttribute("data-testid", "turn-card-0");
    expect(cards[1]).toHaveAttribute("data-testid", "turn-card-1");
  });

  it("renders inline notes below the matching turn", () => {
    const turns = [makeTurn({ index: 0 })];
    const notes = [makeNote({
      turn_index: 0,
      note_type: "hypothesis",
      content: { text: "Default creds likely" },
    })];
    renderTimeline(turns, notes);
    expect(screen.getByText("Default creds likely")).toBeInTheDocument();
    expect(screen.getByText("hypothesis")).toBeInTheDocument();
  });

  it("does not render notes for turns that do not exist", () => {
    const notes = [makeNote({ turn_index: 99 })];
    renderTimeline([], notes);
    expect(screen.queryByText("hypothesis")).not.toBeInTheDocument();
  });

  it("shows truncation hint when isTruncated is true", () => {
    const turns = [makeTurn({ index: 0 })];
    renderTimeline(turns, [], { isTruncated: true });
    expect(screen.getByText(/Showing first/)).toBeInTheDocument();
  });

  it("shows notes truncation hint when isNotesTruncated is true", () => {
    const turns = [makeTurn({ index: 0 })];
    const notes = [makeNote({ turn_index: 0 })];
    renderTimeline(turns, notes, { isNotesTruncated: true });
    expect(screen.getByText(/notebook entries are hidden/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/features/missions/StoryTimeline.test.tsx`
Expected: FAIL — `StoryTimeline` not found.

- [ ] **Step 3: Implement StoryTimeline**

Create `frontend/src/features/missions/StoryTimeline.tsx`:

```tsx
import { useEffect, useRef, useState } from "react";
import type { AgentNote, AgentTurn } from "./types";
import { TurnCard } from "./TurnCard";

type Props = {
  turns: AgentTurn[];
  notes: AgentNote[];
  isLive: boolean;
  isTruncated: boolean;
  isNotesTruncated: boolean;
};

const NOTE_ICONS: Record<string, string> = {
  hypothesis: "💡",
  gap: "❓",
  credential_label: "🔑",
  route: "🔗",
  parameter: "📝",
  candidate: "🎯",
};

const SCROLL_THRESHOLD_PX = 20;

function noteText(note: AgentNote): string {
  if (typeof note.content === "object" && note.content !== null) {
    return (note.content as Record<string, unknown>).text as string ?? JSON.stringify(note.content);
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

function isScrolledUp(el: HTMLElement): boolean {
  return el.scrollTop < el.scrollHeight - el.clientHeight - SCROLL_THRESHOLD_PX;
}

export function StoryTimeline({
  turns,
  notes,
  isLive,
  isTruncated,
  isNotesTruncated,
}: Props) {
  const notesByTurn = groupNotesByTurn(notes);
  const [autoScroll, setAutoScroll] = useState(true);
  const lastRef = useRef<HTMLDivElement | null>(null);
  const prevLenRef = useRef(turns.length);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const prev = prevLenRef.current;
    prevLenRef.current = turns.length;
    if (autoScroll && turns.length > prev && lastRef.current) {
      lastRef.current.scrollIntoView({ block: "end" });
    }
  }, [turns.length, autoScroll]);

  function onScroll(e: React.UIEvent<HTMLDivElement>) {
    if (isScrolledUp(e.currentTarget)) {
      setAutoScroll(false);
    } else {
      setAutoScroll(true);
    }
  }

  if (turns.length === 0) {
    return <p className="text-gray-500 text-center py-8">The agent has not started yet.</p>;
  }

  return (
    <div ref={containerRef} onScroll={onScroll} className="flex-1 overflow-y-auto px-4">
      {isTruncated && (
        <p className="text-sm text-gray-400 text-center py-2">
          Showing first {turns.length} turns
        </p>
      )}
      {turns.map((turn, i) => {
        const turnNotes = notesByTurn.get(turn.index) ?? [];
        return (
          <div key={turn.id} ref={i === turns.length - 1 ? lastRef : undefined}>
            <TurnCard turn={turn} />
            {turnNotes.map((note) => (
              <div
                key={note.id}
                data-testid={`note-${note.id}`}
                className="ml-8 pl-2 border-l-2 border-blue-200 py-1 text-sm text-gray-600"
              >
                <span className="mr-1">{NOTE_ICONS[note.note_type] ?? "📌"}</span>
                <span className="text-xs font-medium text-blue-600 mr-1">{note.note_type}</span>
                {noteText(note)}
              </div>
            ))}
          </div>
        );
      })}
      {isNotesTruncated && (
        <p className="text-sm text-gray-400 text-center py-2">
          Some notebook entries are hidden
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/features/missions/StoryTimeline.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/missions/StoryTimeline.tsx frontend/src/features/missions/StoryTimeline.test.tsx
git commit -m "feat(frontend): StoryTimeline — turn list with inline notes and auto-scroll"
```
