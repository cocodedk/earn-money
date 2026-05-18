import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Table, TableSkeleton } from "./index";

type Row = { id: string; name: string };
const columns = [
  { key: "name", header: "Name", cell: (r: Row) => r.name },
];

describe("Table", () => {
  it("renders rows", () => {
    render(
      <Table<Row>
        columns={columns}
        rows={[{ id: "1", name: "A" }]}
        rowKey={(r) => r.id}
      />,
    );
    expect(screen.getByText("A")).toBeInTheDocument();
  });

  it("renders the empty slot when there are no rows", () => {
    render(
      <Table<Row>
        columns={columns}
        rows={[]}
        rowKey={(r) => r.id}
        emptyState={<div data-testid="custom-empty">Nothing</div>}
      />,
    );
    expect(screen.getByTestId("custom-empty")).toBeInTheDocument();
  });

  it("renders the empty table body when no rows and no empty slot", () => {
    render(<Table<Row> columns={columns} rows={[]} rowKey={(r) => r.id} />);
    expect(screen.getByTestId("table")).toBeInTheDocument();
  });

  it("renders skeleton rows when isLoading, with the same header structure", () => {
    render(
      <Table<Row>
        columns={columns}
        rows={[]}
        rowKey={(r) => r.id}
        isLoading
      />,
    );
    expect(screen.getAllByTestId("skeleton-row")).toHaveLength(5);
    expect(
      screen.getByRole("columnheader", { name: "Name" }),
    ).toBeInTheDocument();
  });

  it("respects column.width when provided", () => {
    render(
      <Table<Row>
        columns={[{ ...columns[0], width: "100px" }]}
        rows={[{ id: "1", name: "A" }]}
        rowKey={(r) => r.id}
      />,
    );
    expect(screen.getByText("Name")).toHaveStyle({ width: "100px" });
  });
});

describe("TableSkeleton", () => {
  it("renders the requested number of rows", () => {
    render(
      <table>
        <TableSkeleton columnCount={2} rowCount={3} />
      </table>,
    );
    expect(screen.getAllByTestId("skeleton-row")).toHaveLength(3);
  });

  it("defaults to 5 rows", () => {
    render(
      <table>
        <TableSkeleton columnCount={2} />
      </table>,
    );
    expect(screen.getAllByTestId("skeleton-row")).toHaveLength(5);
  });
});
