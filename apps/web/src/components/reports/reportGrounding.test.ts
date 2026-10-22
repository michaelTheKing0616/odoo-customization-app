import { describe, expect, it } from "vitest";
import type { FieldRow } from "@/lib/api";
import {
  DEFAULT_USE_EXTERNAL_LAYOUT,
  collectFieldTokens,
  o2mFieldOptions,
  parentFieldOptions,
  refuseEmptyDesign,
  relationalLineFields,
  validateGroundedFields,
} from "./reportGrounding";
import type { ReportBlock } from "./ReportCanvas";

function field(partial: Partial<FieldRow> & { name: string; ttype: string }): FieldRow {
  return {
    id: 1,
    field_description: partial.field_description || partial.name,
    required: false,
    readonly: false,
    relation: partial.relation ?? null,
    state: "base",
    ...partial,
  };
}

describe("reportGrounding PDF-04", () => {
  it("external layout default is on", () => {
    expect(DEFAULT_USE_EXTERNAL_LAYOUT).toBe(true);
  });

  it("field picker helpers only list schema fields", () => {
    const rows = [
      field({ name: "partner_id", ttype: "many2one", relation: "res.partner" }),
      field({ name: "line_ids", ttype: "one2many", relation: "sale.order.line" }),
      field({ name: "display_name", ttype: "char" }),
    ];
    expect(parentFieldOptions(rows).map((r) => r.name)).toEqual([
      "display_name",
      "line_ids",
      "partner_id",
    ]);
    expect(o2mFieldOptions(rows).map((r) => r.name)).toEqual(["line_ids"]);
    expect(relationalLineFields(rows).get("line_ids")).toBe("sale.order.line");
  });

  it("unknown field blocked on save", () => {
    const blocks: ReportBlock[] = [
      { id: "1", type: "field", field: "ghost_field" },
    ];
    expect(
      validateGroundedFields(blocks, new Set(["display_name", "partner_id"])),
    ).toMatch(/unknown field on model: ghost_field/);
  });

  it("empty spec blocked", () => {
    expect(refuseEmptyDesign({ blocks: [] })).toMatch(/empty design/);
    expect(refuseEmptyDesign({ blocks: [{ id: "1", type: "text", text: "Hi" }] })).toBeNull();
  });

  it("o2m columns from related model only", () => {
    const blocks: ReportBlock[] = [
      {
        id: "t",
        type: "o2m_table",
        o2m_field: "line_ids",
        columns: [
          { field: "product_id", label: "Product" },
          { field: "not_on_line", label: "Bad" },
        ],
      },
    ];
    const tokens = collectFieldTokens(blocks);
    expect(tokens.some((t) => t.scope === "column" && t.field === "not_on_line")).toBe(true);
    const err = validateGroundedFields(
      blocks,
      new Set(["line_ids", "display_name"]),
      new Map([["line_ids", new Set(["product_id", "name"])]]),
    );
    expect(err).toMatch(/unknown field on related model for line_ids: not_on_line/);
    expect(
      validateGroundedFields(
        [
          {
            id: "t",
            type: "o2m_table",
            o2m_field: "line_ids",
            columns: [{ field: "product_id", label: "Product" }],
          },
        ],
        new Set(["line_ids"]),
        new Map([["line_ids", new Set(["product_id"])]]),
      ),
    ).toBeNull();
  });
});
