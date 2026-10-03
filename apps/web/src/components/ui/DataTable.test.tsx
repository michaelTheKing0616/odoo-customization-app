/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import {
  DataTable,
  sortDataTableRows,
  type DataTableColumn,
} from "@/components/ui/DataTable";
import {
  BulkResultTable,
  filterBulkResultRows,
  type BulkRunResult,
  type PerRecordResult,
} from "@/components/ui/BulkResultTable";

type Row = { id: string; name: string; score: number };

const columns: DataTableColumn<Row>[] = [
  {
    id: "name",
    header: "Name",
    accessor: (r) => r.name,
    sortValue: (r) => r.name,
  },
  {
    id: "score",
    header: "Score",
    accessor: (r) => r.score,
    sortValue: (r) => r.score,
  },
];

function makeRows(count: number): Row[] {
  return Array.from({ length: count }, (_, i) => ({
    id: `row-${i}`,
    name: `Row ${String(i).padStart(4, "0")}`,
    score: count - 1 - i,
  }));
}

function makeBulkResult(count: number): BulkRunResult {
  const per_record: PerRecordResult[] = Array.from({ length: count }, (_, i) => ({
    record_id: i + 1,
    display_name: `Record ${i + 1}`,
    ok: i % 2 === 0,
    error: i % 2 === 0 ? null : "failed",
  }));
  const succeeded = per_record.filter((r) => r.ok).length;
  return {
    run_id: "run",
    operation: "mass_edit",
    model: "res.partner",
    total: count,
    succeeded,
    failed: count - succeeded,
    per_record,
  };
}

function dataRows() {
  return screen.getByTestId("data-table").querySelectorAll("tbody tr:not([aria-hidden])");
}

afterEach(() => {
  cleanup();
});

describe("DataTable virtualization", () => {
  it("keeps 50 or fewer rows as a normal table", () => {
    render(<DataTable columns={columns} rows={makeRows(50)} rowKey={(r) => r.id} />);
    expect(screen.queryByTestId("data-table-scroll")).not.toBeInTheDocument();
    expect(dataRows()).toHaveLength(50);
  });

  it("virtualizes when rows exceed 50", () => {
    render(<DataTable columns={columns} rows={makeRows(51)} rowKey={(r) => r.id} />);
    expect(screen.getByTestId("data-table-scroll")).toBeInTheDocument();
    expect(dataRows().length).toBeGreaterThan(0);
    expect(dataRows().length).toBeLessThan(51);
  });

  it("honors a caller-supplied virtualizeThreshold", () => {
    const rows = makeRows(200);
    const { rerender } = render(
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(r) => r.id}
        virtualizeThreshold={200}
      />,
    );
    expect(screen.queryByTestId("data-table-scroll")).not.toBeInTheDocument();
    expect(dataRows()).toHaveLength(200);

    rerender(
      <DataTable
        columns={columns}
        rows={makeRows(201)}
        rowKey={(r) => r.id}
        virtualizeThreshold={200}
      />,
    );
    expect(screen.getByTestId("data-table-scroll")).toBeInTheDocument();
    expect(dataRows().length).toBeLessThan(201);
  });
});

describe("DataTable keyboard navigation", () => {
  it("moves the active row with arrows when virtualized", () => {
    render(<DataTable columns={columns} rows={makeRows(80)} rowKey={(r) => r.id} />);
    const grid = screen.getByRole("grid");
    grid.focus();
    expect(grid).toHaveFocus();
    expect(within(grid).getByText("Row 0000").closest("tr")).toHaveAttribute(
      "data-active",
      "true",
    );

    fireEvent.keyDown(grid, { key: "ArrowDown" });
    expect(within(grid).getByText("Row 0001").closest("tr")).toHaveAttribute(
      "data-active",
      "true",
    );
    expect(within(grid).getByText("Row 0000").closest("tr")).not.toHaveAttribute(
      "data-active",
    );

    fireEvent.keyDown(grid, { key: "ArrowUp" });
    expect(within(grid).getByText("Row 0000").closest("tr")).toHaveAttribute(
      "data-active",
      "true",
    );
  });
});

describe("BulkResultTable virtualization", () => {
  it("keeps 50 or fewer records as a normal table", () => {
    render(<BulkResultTable result={makeBulkResult(50)} />);
    expect(screen.queryByTestId("data-table-scroll")).not.toBeInTheDocument();
    expect(dataRows()).toHaveLength(50);
  });

  it("virtualizes when records exceed 50", () => {
    render(<BulkResultTable result={makeBulkResult(51)} />);
    expect(screen.getByTestId("data-table-scroll")).toBeInTheDocument();
    expect(dataRows().length).toBeGreaterThan(0);
    expect(dataRows().length).toBeLessThan(51);
  });
});

describe("sort and filter performance", () => {
  it("sorts and filters 5000 rows in under 100ms", () => {
    const rows = makeRows(5000);
    const records = makeBulkResult(5000).per_record;

    const started = performance.now();
    const sorted = sortDataTableRows(rows, columns, { id: "score", dir: "asc" });
    const filtered = filterBulkResultRows(records, "failed");
    const elapsedMs = performance.now() - started;

    expect(sorted).toHaveLength(5000);
    expect(sorted[0]?.score).toBe(0);
    expect(sorted[4999]?.score).toBe(4999);
    expect(filtered).toHaveLength(2500);
    expect(filtered.every((r) => !r.ok)).toBe(true);
    expect(elapsedMs).toBeLessThan(100);
    // eslint-disable-next-line no-console
    console.info(`UI-F11 5000-row sort+filter: ${elapsedMs.toFixed(3)}ms`);
  });
});
