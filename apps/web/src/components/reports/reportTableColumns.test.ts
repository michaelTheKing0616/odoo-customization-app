import { describe, expect, it } from "vitest";
import type { FieldRow } from "@/lib/api";
import {
  changeColumnField,
  columnDefaultAlign,
  columnFromField,
  columnWidthMode,
  fixedWidthTotal,
  formatWidthPct,
  nextUnusedField,
  normalizeTableBlockColumns,
  normalizeTableColumn,
  parseColumnWidth,
  resolveColumnAlign,
  resolveColumnWidths,
  tableEmitsTotals,
  validateTableTotals,
} from "./reportTableColumns";
import { collectFieldTokens, validateGroundedFields } from "./reportGrounding";
import { refuseUnsafeBlockText } from "./reportUnsafeGate";
import type { ReportBlock } from "./ReportCanvas";

function row(name: string, ttype: string, label = name): FieldRow {
  return {
    id: 1,
    name,
    field_description: label,
    ttype,
    required: false,
    readonly: false,
    relation: null,
    state: "base",
  } as FieldRow;
}

describe("PDF-07 column align", () => {
  it("defaults left, right for numeric ttype; explicit align wins", () => {
    expect(columnDefaultAlign("char")).toBe("left");
    expect(columnDefaultAlign(undefined)).toBe("left");
    expect(columnDefaultAlign("float")).toBe("right");
    expect(columnDefaultAlign("monetary")).toBe("right");
    expect(columnDefaultAlign("integer")).toBe("right");
    expect(resolveColumnAlign({ field: "a", ttype: "float" })).toBe("right");
    expect(resolveColumnAlign({ field: "a", ttype: "float", align: "left" })).toBe("left");
    expect(resolveColumnAlign({ field: "a", align: "center" })).toBe("center");
  });

  it("ignores bogus align values", () => {
    expect(
      resolveColumnAlign({ field: "a", align: 'right" onload="x' as never }),
    ).toBe("left");
  });
});

describe("PDF-07 column width (mirrors report_design.py)", () => {
  it("parses percent, fr and plain numbers", () => {
    expect(parseColumnWidth(25)).toEqual({ unit: "pct", value: 25 });
    expect(parseColumnWidth("25%")).toEqual({ unit: "pct", value: 25 });
    expect(parseColumnWidth(" 12.5 ")).toEqual({ unit: "pct", value: 12.5 });
    expect(parseColumnWidth("2fr")).toEqual({ unit: "fr", value: 2 });
  });

  it.each([
    "10px; color:red",
    "expression(alert(1))",
    "50%; background:url(x)",
    "calc(10% + 2px)",
    "0",
    -5,
    101,
    "1e3",
    true,
    "",
    null,
    undefined,
    Number.NaN,
    Number.POSITIVE_INFINITY,
    {},
  ])("rejects %p", (raw) => {
    expect(parseColumnWidth(raw)).toBeNull();
  });

  it("resolves fr against what fixed % leave; auto stays null", () => {
    expect(
      resolveColumnWidths([
        { field: "a", width: "2fr" },
        { field: "b", width: 15 },
        { field: "c", width: "20%" },
      ]),
    ).toEqual([65, 15, 20]);
    expect(
      resolveColumnWidths([
        { field: "a", width: "1fr" },
        { field: "b", width: "2fr" },
        { field: "c" },
        { field: "d", width: "40" },
      ]),
    ).toEqual([20, 40, null, 40]);
    expect(resolveColumnWidths([{ field: "a", width: "1fr" }, { field: "b", width: 100 }])).toEqual([
      null,
      100,
    ]);
    expect(formatWidthPct(33.333)).toBe("33.33%");
    expect(formatWidthPct(25)).toBe("25%");
  });

  it("reports width mode and fixed total", () => {
    expect(columnWidthMode({ field: "a" })).toBe("auto");
    expect(columnWidthMode({ field: "a", width: 20 })).toBe("pct");
    expect(columnWidthMode({ field: "a", width: "1fr" })).toBe("fr");
    expect(columnWidthMode({ field: "a", width: "10px" })).toBe("auto");
    expect(fixedWidthTotal([{ field: "a", width: 60 }, { field: "b", width: "50%" }, { field: "c", width: "1fr" }])).toBe(110);
  });
});

describe("PDF-07 normalize / field changes", () => {
  it("normalizes persisted columns and drops junk", () => {
    expect(
      normalizeTableColumn({
        field: " qty ",
        label: "Qty",
        align: "diagonal",
        width: "10px; color:red",
        sum: "yes",
        style: "color:red",
      }),
    ).toEqual({ field: "qty", label: "Qty" });
    expect(
      normalizeTableColumn({ field: "qty", label: "Q", align: "right", width: "2fr", sum: true, ttype: "float" }),
    ).toEqual({ field: "qty", label: "Q", align: "right", width: "2fr", sum: true, ttype: "float" });
    expect(normalizeTableColumn({ label: "no field" })).toBeNull();
    const block = normalizeTableBlockColumns({
      type: "o2m_table",
      o2m_field: "order_line",
      columns: [null as never, { field: "" } as never],
      totals_row: "yes" as never,
      totals_label: 5 as never,
    });
    expect(block.columns).toEqual([{ field: "display_name", label: "Line" }]);
    expect(block.totals_row).toBe(false);
    expect("totals_label" in block).toBe(false);
    // Non-table blocks are untouched
    const text = { type: "text", text: "hi" };
    expect(normalizeTableBlockColumns(text)).toBe(text);
  });

  it("columnFromField seeds label, ttype and numeric right-align", () => {
    expect(columnFromField(row("price_subtotal", "monetary", "Subtotal"))).toEqual({
      field: "price_subtotal",
      label: "Subtotal",
      ttype: "monetary",
      align: "right",
    });
    expect(columnFromField(row("name", "char", "Description"))).toEqual({
      field: "name",
      label: "Description",
      ttype: "char",
    });
    expect(columnFromField(undefined)).toEqual({ field: "display_name", label: "Line" });
  });

  it("changeColumnField keeps width + user align, drops sum on non-numeric", () => {
    const col = { field: "price_subtotal", label: "Subtotal", ttype: "monetary", align: "right" as const, width: 20, sum: true };
    const toChar = changeColumnField(col, row("name", "char", "Description"), "name");
    expect(toChar).toEqual({ field: "name", label: "Description", ttype: "char", width: 20 });
    const centered = { ...col, align: "center" as const };
    expect(changeColumnField(centered, row("qty", "float", "Qty"), "qty")).toEqual({
      field: "qty",
      label: "Qty",
      ttype: "float",
      align: "center",
      width: 20,
      sum: true,
    });
  });

  it("nextUnusedField prefers a field not already a column", () => {
    const fields = [row("name", "char"), row("qty", "float")];
    expect(nextUnusedField([{ field: "name", label: "N" }], fields)?.name).toBe("qty");
    expect(nextUnusedField([{ field: "name", label: "N" }, { field: "qty", label: "Q" }], fields)?.name).toBe("name");
    expect(nextUnusedField([], [])).toBeUndefined();
  });
});

describe("PDF-07 totals + grounding", () => {
  const table: ReportBlock = {
    id: "t",
    type: "o2m_table",
    o2m_field: "order_line",
    totals_row: true,
    totals_label: "Grand total",
    columns: [
      { field: "name", label: "Desc", align: "left", width: "2fr" },
      { field: "price_subtotal", label: "Subtotal", sum: true, width: 20, align: "right" },
    ],
  };

  it("emits totals only when on and a column sums", () => {
    expect(tableEmitsTotals(table)).toBe(true);
    expect(tableEmitsTotals({ ...table, totals_row: false })).toBe(false);
    expect(
      tableEmitsTotals({ ...table, columns: table.columns!.map((c) => ({ ...c, sum: false })) }),
    ).toBe(false);
  });

  it("refuses sums on non-numeric related fields", () => {
    const types = new Map([["order_line", new Map([["name", "char"], ["price_subtotal", "monetary"]])]]);
    expect(validateTableTotals([table], types)).toBeNull();
    const bad: ReportBlock = { ...table, columns: [{ field: "name", label: "D", sum: true }] };
    expect(validateTableTotals([bad], types)).toMatch(/only sum numeric fields; order_line.name is char/);
    // unknown related schema → leave it to field grounding
    expect(validateTableTotals([bad], new Map())).toBeNull();
  });

  it("align/width/totals never add field tokens; unknown columns still refused", () => {
    expect(collectFieldTokens([table])).toEqual([
      { scope: "parent", field: "order_line" },
      { scope: "column", field: "name", o2m_field: "order_line" },
      { scope: "column", field: "price_subtotal", o2m_field: "order_line" },
    ]);
    const ghost: ReportBlock = {
      ...table,
      columns: [{ field: "ghost", label: "G", align: "right", width: 30, sum: true }],
    };
    expect(
      validateGroundedFields([ghost], new Set(["order_line"]), {
        order_line: new Set(["name", "price_subtotal"]),
      }),
    ).toMatch(/unknown field on related model for order_line: ghost/);
  });

  it("PDF-05 gate refuses QWeb in the totals caption", () => {
    expect(refuseUnsafeBlockText([table])).toBeNull();
    expect(refuseUnsafeBlockText([{ ...table, totals_label: '<t t-esc="1"/>' }])).toMatch(
      /totals_label must not contain QWeb/,
    );
  });
});
