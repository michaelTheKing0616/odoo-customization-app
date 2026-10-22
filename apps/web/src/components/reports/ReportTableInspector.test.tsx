/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { FieldRow } from "@/lib/api";
import type { ReportBlock } from "./ReportCanvas";
import { ReportCanvas } from "./ReportCanvas";
import { ReportTableInspector } from "./ReportTableInspector";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function row(id: number, name: string, ttype: string, label: string, relation: string | null = null): FieldRow {
  return {
    id,
    name,
    field_description: label,
    ttype,
    required: false,
    readonly: false,
    relation,
    state: "base",
  } as FieldRow;
}

const o2mOptions = [row(3, "order_line", "one2many", "Order Lines", "sale.order.line")];
const lineFields = [
  row(11, "name", "char", "Description"),
  row(12, "product_uom_qty", "float", "Quantity"),
  row(13, "price_subtotal", "monetary", "Subtotal"),
  row(14, "sequence", "integer", "Sequence"),
];

const baseBlock: ReportBlock = {
  id: "lines",
  type: "o2m_table",
  o2m_field: "order_line",
  columns: [
    { field: "name", label: "Description" },
    { field: "product_uom_qty", label: "Qty" },
    { field: "price_subtotal", label: "Subtotal" },
  ],
};

let latest: ReportBlock = baseBlock;

function Harness({
  initial = baseBlock,
  fields = lineFields,
  withCanvas = false,
}: {
  initial?: ReportBlock;
  fields?: FieldRow[];
  withCanvas?: boolean;
}) {
  const [block, setBlock] = useState<ReportBlock>(initial);
  const [active, setActive] = useState(0);
  latest = block;
  return (
    <>
      <ReportTableInspector
        block={block}
        o2mOptions={o2mOptions}
        relatedFields={fields}
        activeIndex={active}
        onActiveIndexChange={setActive}
        onChange={(patch) => setBlock((prev) => ({ ...prev, ...patch }))}
      />
      {withCanvas ? (
        <ReportCanvas
          blocks={[block]}
          selectedId={block.id}
          activeColumn={{ blockId: block.id, index: active }}
          onSelectColumn={(_id, i) => setActive(i)}
        />
      ) : null}
    </>
  );
}

describe("ReportTableInspector PDF-07", () => {
  it("lists columns with grounded field pickers (related model only)", () => {
    render(<Harness />);
    expect(screen.getByTestId("report-table-inspector")).toBeTruthy();
    expect(screen.getByTestId("report-o2m-columns").querySelectorAll("[data-reorder-item]")).toHaveLength(3);
    const picker = screen.getByTestId("report-o2m-column-field-0") as HTMLSelectElement;
    const values = Array.from(picker.options).map((o) => o.value);
    expect(values).toEqual(["name", "product_uom_qty", "price_subtotal", "sequence"]);
  });

  it("align segmented control sets align; numeric columns default right", () => {
    render(<Harness />);
    expect(screen.getByTestId("report-table-align-left")).toHaveAttribute("aria-checked", "true");
    fireEvent.click(screen.getByTestId("report-table-column-row-2"));
    // price_subtotal is monetary → right by default (no explicit align stored)
    expect(screen.getByTestId("report-table-align-right")).toHaveAttribute("aria-checked", "true");
    expect(latest.columns?.[2].align).toBeUndefined();
    fireEvent.click(screen.getByTestId("report-table-align-center"));
    expect(latest.columns?.[2].align).toBe("center");
    expect(screen.getByTestId("report-table-align-center")).toHaveAttribute("aria-checked", "true");
  });

  it("width control: % input, flex weight, auto clears", () => {
    render(<Harness />);
    expect(screen.getByTestId("report-table-width-resolved")).toHaveTextContent("auto");
    fireEvent.click(screen.getByTestId("report-table-width-mode-pct"));
    expect(latest.columns?.[0].width).toBe(20);
    fireEvent.change(screen.getByTestId("report-table-width-input"), { target: { value: "45" } });
    expect(latest.columns?.[0].width).toBe(45);
    expect(screen.getByTestId("report-table-width-resolved")).toHaveTextContent("45%");
    // invalid input is not committed
    fireEvent.change(screen.getByTestId("report-table-width-input"), { target: { value: "500" } });
    expect(latest.columns?.[0].width).toBe(45);
    expect(screen.getByTestId("report-table-width-input")).toHaveAttribute("aria-invalid", "true");
    fireEvent.click(screen.getByTestId("report-table-width-mode-fr"));
    expect(latest.columns?.[0].width).toBe("1fr");
    expect(screen.getByTestId("report-table-width-resolved")).toHaveTextContent("100%");
    fireEvent.change(screen.getByTestId("report-table-width-input"), { target: { value: "3" } });
    expect(latest.columns?.[0].width).toBe("3fr");
    fireEvent.click(screen.getByTestId("report-table-width-mode-auto"));
    expect(latest.columns?.[0]).not.toHaveProperty("width");
    expect(screen.queryByTestId("report-table-width-input")).toBeNull();
  });

  it("warns when fixed widths exceed 100%", () => {
    render(
      <Harness
        initial={{
          ...baseBlock,
          columns: [
            { field: "name", label: "D", width: 70 },
            { field: "price_subtotal", label: "S", width: 40 },
          ],
        }}
      />,
    );
    expect(screen.getByTestId("report-table-width-warning")).toHaveTextContent("110%");
    expect(screen.getByTestId("report-table-width-budget")).toHaveAttribute("data-over", "true");
  });

  it("add column picks an unused grounded field; remove keeps at least one", () => {
    render(<Harness />);
    fireEvent.click(screen.getByTestId("report-o2m-add-column"));
    expect(latest.columns).toHaveLength(4);
    expect(latest.columns?.[3]).toEqual({
      field: "sequence",
      label: "Sequence",
      ttype: "integer",
      align: "right",
    });
    // new column becomes active in the editor
    expect(screen.getByTestId("report-o2m-column-field-3")).toHaveValue("sequence");
    for (let i = 3; i >= 0; i -= 1) {
      fireEvent.click(screen.getByTestId(`report-table-column-remove-${i}`));
    }
    expect(latest.columns).toEqual([{ field: "display_name", label: "Line" }]);
  });

  it("keyboard arrows reorder columns and focus follows the moved column", () => {
    render(<Harness />);
    const first = screen.getByTestId("report-table-column-row-0");
    fireEvent.keyDown(first, { key: "ArrowDown" });
    expect(latest.columns?.map((c) => c.field)).toEqual(["product_uom_qty", "name", "price_subtotal"]);
    expect(screen.getByTestId("report-table-column-row-1")).toHaveAttribute("aria-pressed", "true");
    fireEvent.keyDown(screen.getByTestId("report-table-column-row-1"), { key: "ArrowUp" });
    expect(latest.columns?.map((c) => c.field)).toEqual(["name", "product_uom_qty", "price_subtotal"]);
  });

  it("pointer drag reorders columns via ReorderableBlocks", () => {
    render(<Harness />);
    const list = screen.getByTestId("report-o2m-columns");
    vi.spyOn(list, "getBoundingClientRect").mockReturnValue({
      x: 0, y: 0, width: 200, height: 90, top: 0, left: 0, right: 200, bottom: 90, toJSON: () => ({}),
    } as DOMRect);
    const rows = Array.from(list.querySelectorAll<HTMLElement>("[data-reorder-item]"));
    rows.forEach((el, i) => {
      vi.spyOn(el, "getBoundingClientRect").mockReturnValue({
        x: 0, y: i * 30, width: 200, height: 30, top: i * 30, left: 0, right: 200, bottom: i * 30 + 30, toJSON: () => ({}),
      } as DOMRect);
    });
    const first = rows[0];
    fireEvent.pointerDown(first, { pointerId: 1, button: 0, clientX: 10, clientY: 10 });
    fireEvent.pointerMove(first, { pointerId: 1, clientX: 10, clientY: 85 });
    fireEvent.pointerUp(first, { pointerId: 1, clientX: 10, clientY: 85 });
    expect(latest.columns?.map((c) => c.field)).toEqual(["product_uom_qty", "price_subtotal", "name"]);
  });

  it("totals toggle pre-marks numeric columns; sum disabled for non-numeric", () => {
    render(<Harness />);
    expect(screen.queryByTestId("report-table-col-sum")).toBeNull();
    fireEvent.click(screen.getByTestId("report-table-totals-toggle"));
    expect(latest.totals_row).toBe(true);
    expect(latest.columns?.map((c) => c.sum === true)).toEqual([false, true, true]);
    // active column 0 is char → switch disabled with hint
    expect(screen.getByTestId("report-table-col-sum")).toBeDisabled();
    expect(screen.getByTestId("report-table-col-sum-hint")).toBeTruthy();
    fireEvent.click(screen.getByTestId("report-table-column-row-1"));
    const sw = screen.getByTestId("report-table-col-sum");
    expect(sw).not.toBeDisabled();
    expect(sw).toHaveAttribute("aria-checked", "true");
    fireEvent.click(sw);
    expect(latest.columns?.[1]).not.toHaveProperty("sum");
    fireEvent.change(screen.getByTestId("report-table-totals-label"), { target: { value: "Grand total" } });
    expect(latest.totals_label).toBe("Grand total");
    fireEvent.click(screen.getByTestId("report-table-totals-toggle"));
    expect(latest.totals_row).toBe(false);
  });

  it("totals with no numeric columns shows guidance instead of an empty footer", () => {
    render(
      <Harness initial={{ ...baseBlock, columns: [{ field: "name", label: "D" }] }} />,
    );
    fireEvent.click(screen.getByTestId("report-table-totals-toggle"));
    expect(screen.getByTestId("report-table-totals-empty")).toBeTruthy();
  });

  it("flags columns that are not on the related model", () => {
    render(
      <Harness initial={{ ...baseBlock, columns: [{ field: "ghost", label: "Ghost" }] }} />,
    );
    expect(screen.getByTestId("report-table-column-orphan-0")).toHaveTextContent("not on model");
  });

  it("changing a column field resets type defaults and drops an invalid sum", () => {
    render(
      <Harness
        initial={{
          ...baseBlock,
          totals_row: true,
          columns: [{ field: "price_subtotal", label: "Subtotal", ttype: "monetary", sum: true, width: 25 }],
        }}
      />,
    );
    fireEvent.change(screen.getByTestId("report-o2m-column-field-0"), { target: { value: "name" } });
    expect(latest.columns?.[0]).toEqual({ field: "name", label: "Description", ttype: "char", width: 25 });
  });

  it("canvas reflects align, width and totals; header click focuses the column", () => {
    render(
      <Harness
        withCanvas
        initial={{
          ...baseBlock,
          totals_row: true,
          columns: [
            { field: "name", label: "Description", width: "2fr" },
            { field: "product_uom_qty", label: "Qty", ttype: "float", width: 15, align: "center" },
            { field: "price_subtotal", label: "Subtotal", ttype: "monetary", width: "20%", sum: true },
          ],
        }}
      />,
    );
    const table = screen.getByTestId("report-table-lines");
    const ths = Array.from(table.querySelectorAll("thead th")) as HTMLElement[];
    expect(ths.map((th) => th.style.width)).toEqual(["65%", "15%", "20%"]);
    expect(ths.map((th) => th.style.textAlign)).toEqual(["left", "center", "right"]);
    expect(ths.map((th) => th.getAttribute("data-align"))).toEqual(["left", "center", "right"]);
    const foot = screen.getByTestId("report-table-totals-lines");
    expect(foot).toHaveTextContent("Total");
    expect(foot.querySelectorAll("[data-sum-cell='true']")).toHaveLength(1);
    fireEvent.click(ths[2]);
    expect(screen.getByTestId("report-o2m-column-field-2")).toHaveValue("price_subtotal");
    expect(ths[2]).toHaveAttribute("data-active-col", "true");
    // inspector edit → paper updates
    fireEvent.click(screen.getByTestId("report-table-align-left"));
    expect((table.querySelectorAll("thead th")[2] as HTMLElement).style.textAlign).toBe("left");
  });
});
