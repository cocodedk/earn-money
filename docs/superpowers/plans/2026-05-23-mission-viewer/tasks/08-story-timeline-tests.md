# Task 8 — Tests: StoryTimeline

Test code for [Task 8](08-story-timeline.md).

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
    expect(
      screen.getByText("The agent has not started yet."),
    ).toBeInTheDocument();
  });

  it("renders turns in ascending order", () => {
    const turns = [
      makeTurn({
        index: 1,
        id: "t-2",
        actions: [makeAction({ goal: "Second", id: "a-2" })],
      }),
      makeTurn({ index: 0, actions: [makeAction({ goal: "First" })] }),
    ];
    renderTimeline(turns);
    const cards = screen.getAllByTestId(/^turn-card-/);
    expect(cards).toHaveLength(2);
    expect(cards[0]).toHaveAttribute("data-testid", "turn-card-0");
    expect(cards[1]).toHaveAttribute("data-testid", "turn-card-1");
  });

  it("marks the timeline as live when isLive is true", () => {
    renderWithProviders(
      <StoryTimeline
        turns={[makeTurn({ index: 0 })]}
        notes={[]}
        isLive={true}
        isTruncated={false}
        isNotesTruncated={false}
      />,
    );
    expect(screen.getByLabelText("Live mission timeline")).toBeInTheDocument();
  });

  it("renders inline notes below the matching turn", () => {
    const turns = [makeTurn({ index: 0 })];
    const notes = [
      makeNote({
        turn_index: 0,
        note_type: "hypothesis",
        content: { text: "Default creds likely" },
      }),
    ];
    renderTimeline(turns, notes);
    expect(screen.getByText("Default creds likely")).toBeInTheDocument();
    expect(screen.getByText("hypothesis")).toBeInTheDocument();
  });

  it("does not render notes for non-existent turns", () => {
    const notes = [makeNote({ turn_index: 99 })];
    renderTimeline([], notes);
    expect(screen.queryByText("hypothesis")).not.toBeInTheDocument();
  });

  it("shows truncation hint when isTruncated is true", () => {
    const turns = [makeTurn({ index: 0 })];
    renderTimeline(turns, [], { isTruncated: true });
    expect(screen.getByText(/Showing first/)).toBeInTheDocument();
  });

  it("shows notes truncation hint", () => {
    const turns = [makeTurn({ index: 0 })];
    const notes = [makeNote({ turn_index: 0 })];
    renderTimeline(turns, notes, { isNotesTruncated: true });
    expect(
      screen.getByText(/notebook entries are hidden/i),
    ).toBeInTheDocument();
  });
});
```
