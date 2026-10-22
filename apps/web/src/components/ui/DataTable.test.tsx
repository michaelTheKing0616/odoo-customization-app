/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { VirtuosoMockContext } from "react-virtuoso";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
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

describe("DataTable threshold switch", () => {
  it("switches between plain and virtual markup when rows cross the threshold", () => {
    const { rerender } = render(
      <DataTable columns={columns} rows={makeRows(50)} rowKey={(r) => r.id} />,
    );
    expect(screen.queryByTestId("data-table-scroll")).not.toBeInTheDocument();
    expect(dataRows()).toHaveLength(50);

    rerender(<DataTable columns={columns} rows={makeRows(51)} rowKey={(r) => r.id} />);
    expect(screen.getByTestId("data-table-scroll")).toBeInTheDocument();
    expect(dataRows().length).toBeLessThan(51);

    rerender(<DataTable columns={columns} rows={makeRows(50)} rowKey={(r) => r.id} />);
    expect(screen.queryByTestId("data-table-scroll")).not.toBeInTheDocument();
    expect(dataRows()).toHaveLength(50);
  });

  it("keeps the plain path keyboard-operable below the threshold", () => {
    render(<DataTable columns={columns} rows={makeRows(10)} rowKey={(r) => r.id} />);
    const grid = screen.getByRole("grid");
    grid.focus();
    fireEvent.keyDown(grid, { key: "ArrowDown" });
    const row = within(grid).getByText("Row 0001").closest("tr");
    expect(row).toHaveAttribute("data-active", "true");
    expect(grid).toHaveAttribute("aria-activedescendant", row?.id);
  });
});

describe("DataTable aria-rowcount", () => {
  it("counts every data row plus the header when virtualized", () => {
    render(<DataTable columns={columns} rows={makeRows(5000)} rowKey={(r) => r.id} />);
    const grid = screen.getByRole("grid");
    expect(dataRows().length).toBeLessThan(5000);
    expect(grid).toHaveAttribute("aria-rowcount", "5001");
    expect(grid.querySelector("thead tr")).toHaveAttribute("aria-rowindex", "1");
    const rendered = Array.from(dataRows());
    rendered.forEach((tr) => {
      const label = within(tr as HTMLElement).getByText(/^Row \d{4}$/).textContent ?? "";
      const dataIndex = Number(label.slice(4));
      expect(tr).toHaveAttribute("aria-rowindex", String(dataIndex + 2));
    });
  });

  it("matches the plain path below the threshold", () => {
    render(<DataTable columns={columns} rows={makeRows(20)} rowKey={(r) => r.id} />);
    const grid = screen.getByRole("grid");
    expect(grid).toHaveAttribute("aria-rowcount", "21");
    expect(dataRows()[19]).toHaveAttribute("aria-rowindex", "21");
  });

  it("omits aria-rowcount while loading or empty", () => {
    const { rerender } = render(
      <DataTable columns={columns} rows={[]} rowKey={(r) => r.id} loading />,
    );
    expect(screen.getByRole("grid")).not.toHaveAttribute("aria-rowcount");
    rerender(<DataTable columns={columns} rows={[]} rowKey={(r) => r.id} />);
    expect(screen.getByRole("grid")).not.toHaveAttribute("aria-rowcount");
  });

  it("marks the sorted column with aria-sort", () => {
    render(<DataTable columns={columns} rows={makeRows(80)} rowKey={(r) => r.id} />);
    const scoreHeader = screen.getByRole("columnheader", { name: /Score/ });
    expect(scoreHeader).toHaveAttribute("aria-sort", "none");
    fireEvent.click(within(scoreHeader).getByRole("button"));
    expect(scoreHeader).toHaveAttribute("aria-sort", "ascending");
    expect(within(screen.getByRole("grid")).getByText("Row 0079").closest("tr")).toHaveAttribute(
      "aria-rowindex",
      "2",
    );
  });
});

describe("DataTable keyboard navigation beyond the viewport", () => {
  // jsdom has no layout, so Element.scrollTo neither moves nor emits "scroll"; emulate both.
  const originalScrollTo = HTMLElement.prototype.scrollTo;
  beforeEach(() => {
    HTMLElement.prototype.scrollTo = function scrollTo(
      this: HTMLElement,
      options?: ScrollToOptions | number,
    ) {
      const top = typeof options === "object" ? options?.top : undefined;
      if (typeof top === "number") this.scrollTop = top;
      queueMicrotask(() => this.dispatchEvent(new Event("scroll")));
    } as typeof HTMLElement.prototype.scrollTo;
  });
  afterEach(() => {
    HTMLElement.prototype.scrollTo = originalScrollTo;
  });

  it("renders and activates a row that started outside the virtual window", async () => {
    render(
      <VirtuosoMockContext.Provider value={{ viewportHeight: 360, itemHeight: 40 }}>
        <DataTable columns={columns} rows={makeRows(500)} rowKey={(r) => r.id} />
      </VirtuosoMockContext.Provider>,
    );
    const grid = screen.getByRole("grid");
    expect(within(grid).queryByText("Row 0030")).not.toBeInTheDocument();
    const scroller = screen.getByTestId("data-table-scroll");
    Object.defineProperty(scroller, "offsetHeight", { configurable: true, value: 360 });
    Object.defineProperty(scroller, "scrollHeight", { configurable: true, value: 500 * 40 });
    scroller.getBoundingClientRect = () => ({ height: 360, width: 800 }) as DOMRect;

    grid.focus();
    for (let i = 0; i < 30; i += 1) fireEvent.keyDown(grid, { key: "ArrowDown" });

    expect(grid).toHaveAttribute("aria-activedescendant", "data-table-row-row-30");
    const row = await waitFor(() => {
      const el = within(grid).getByText("Row 0030").closest("tr");
      expect(el).not.toBeNull();
      return el!;
    });
    expect(row).toHaveAttribute("id", "data-table-row-row-30");
    expect(row).toHaveAttribute("data-active", "true");
    expect(row).toHaveAttribute("aria-rowindex", "32");
    expect(grid).toHaveAttribute("aria-rowcount", "501");
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
