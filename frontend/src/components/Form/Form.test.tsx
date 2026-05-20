import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FormField, TextInput, Textarea } from "./index";

describe("FormField + TextInput", () => {
  it("wires label, input, and error message", () => {
    render(
      <FormField label="Name" htmlFor="name" error="already exists" required>
        <TextInput id="name" defaultValue="" />
      </FormField>,
    );
    const input = screen.getByLabelText(/Name/);
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAttribute("aria-describedby", "name-error");
    expect(screen.getByText("already exists")).toHaveAttribute("id", "name-error");
  });

  it("accepts typing", async () => {
    render(
      <FormField label="Name" htmlFor="name">
        <TextInput id="name" defaultValue="" />
      </FormField>,
    );
    await userEvent.type(screen.getByLabelText("Name"), "Alpha");
    expect(screen.getByLabelText("Name")).toHaveValue("Alpha");
  });

  it("omits the required marker when required is false", () => {
    render(
      <FormField label="Name" htmlFor="name">
        <TextInput id="name" defaultValue="" />
      </FormField>,
    );
    expect(screen.queryByText("*")).not.toBeInTheDocument();
  });
});

describe("Textarea", () => {
  it("renders multiline", async () => {
    render(<Textarea id="d" defaultValue="" />);
    await userEvent.type(screen.getByRole("textbox"), "x\ny");
    expect(screen.getByRole("textbox")).toHaveValue("x\ny");
  });
});
