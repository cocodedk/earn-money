import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/renderWithProviders";
import { DiscoveryChips } from "./DiscoveryChips";
import { makeTurn, makeNote, makeAction, makeObservation } from "./__fixtures__/mission";

describe("DiscoveryChips", () => {
  it("renders chips from route notes", () => {
    const turn = makeTurn();
    const notes = [
      makeNote({ note_type: "route", content: { text: "/login" } }),
      makeNote({ note_type: "route", content: { text: "/admin" }, id: "n-2" }),
    ];
    renderWithProviders(<DiscoveryChips turn={turn} notes={notes} />);
    expect(screen.getByText("/login")).toBeInTheDocument();
    expect(screen.getByText("/admin")).toBeInTheDocument();
  });

  it("caps at 3 and shows +N more", () => {
    const turn = makeTurn({
      actions: [makeAction({
        observations: [makeObservation({
          data: {
            discovered: { routes: ["/a", "/b", "/c", "/d", "/e"], assets: [] },
          },
        })],
      })],
    });
    renderWithProviders(<DiscoveryChips turn={turn} notes={[]} />);
    expect(screen.getByTestId("chips-expand")).toHaveTextContent("+2 more");
  });

  it("expands on click", async () => {
    const user = userEvent.setup();
    const turn = makeTurn({
      actions: [makeAction({
        observations: [makeObservation({
          data: { discovered: { routes: ["/a", "/b", "/c", "/d"], assets: [] } },
        })],
      })],
    });
    renderWithProviders(<DiscoveryChips turn={turn} notes={[]} />);
    await user.click(screen.getByTestId("chips-expand"));
    expect(screen.getByText("/d")).toBeInTheDocument();
    expect(screen.queryByTestId("chips-expand")).not.toBeInTheDocument();
  });

  it("returns null when no chips", () => {
    const turn = makeTurn({ actions: [makeAction({ observations: [] })] });
    const { container } = renderWithProviders(
      <DiscoveryChips turn={turn} notes={[]} />,
    );
    expect(container.innerHTML).toBe("");
  });
});
