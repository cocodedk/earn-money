import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FiltersBar } from "./FiltersBar";

describe("FiltersBar", () => {
  it("renders each filter as a labelled select with an 'All' sentinel", () => {
    render(
      <FiltersBar
        filters={[
          {
            key: "severity",
            label: "Severity",
            options: [
              { value: "info", label: "Info" },
              { value: "high", label: "High" },
            ],
          },
        ]}
        values={{}}
        onChange={() => {}}
      />,
    );
    const select = screen.getByLabelText("Severity");
    const optionTexts = Array.from(
      select.querySelectorAll("option"),
      (o) => (o as HTMLOptionElement).textContent,
    );
    expect(optionTexts).toEqual(["All", "Info", "High"]);
  });

  it("reflects values[key] as the selected option", () => {
    render(
      <FiltersBar
        filters={[
          {
            key: "severity",
            label: "Severity",
            options: [
              { value: "info", label: "Info" },
              { value: "high", label: "High" },
            ],
          },
        ]}
        values={{ severity: "high" }}
        onChange={() => {}}
      />,
    );
    expect(
      (screen.getByLabelText("Severity") as HTMLSelectElement).value,
    ).toBe("high");
  });

  it("fires onChange(key, newValue) when select changes", async () => {
    const onChange = vi.fn();
    render(
      <FiltersBar
        filters={[
          {
            key: "severity",
            label: "Severity",
            options: [{ value: "high", label: "High" }],
          },
        ]}
        values={{}}
        onChange={onChange}
      />,
    );
    await userEvent.selectOptions(screen.getByLabelText("Severity"), "high");
    expect(onChange).toHaveBeenCalledWith("severity", "high");
  });

  it("renders a text input when inputType=text", async () => {
    const onChange = vi.fn();
    render(
      <FiltersBar
        filters={[
          { key: "source", label: "Source", options: [], inputType: "text" },
        ]}
        values={{ source: "" }}
        onChange={onChange}
      />,
    );
    const input = screen.getByLabelText("Source") as HTMLInputElement;
    expect(input).toHaveAttribute("type", "text");
    await userEvent.type(input, "x");
    expect(onChange).toHaveBeenCalledWith("source", "x");
  });

  it("falls back to a select with just 'All' when options is empty (default mode)", () => {
    render(
      <FiltersBar
        filters={[{ key: "project", label: "Project", options: [] }]}
        values={{}}
        onChange={() => {}}
      />,
    );
    const select = screen.getByLabelText("Project") as HTMLSelectElement;
    expect(select.tagName).toBe("SELECT");
    expect(select.options).toHaveLength(1);
    expect(select.options[0].textContent).toBe("All");
  });
});
