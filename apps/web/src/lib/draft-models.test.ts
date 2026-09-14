import { describe, expect, it } from "vitest";
import {
  formSlotCatalog,
  inheritPlacementRows,
  inheritHostModelFromDraft,
  isFieldPackDraft,
  primaryCustomModelFromDraft,
  refineSuggestionsFromDraft,
  viewDesignerHref,
} from "./draft-models";

describe("primaryCustomModelFromDraft", () => {
  it("picks the first custom x_* that is not a line model", () => {
    expect(
      primaryCustomModelFromDraft({
        models: [
          { model: "x_ticket_line" },
          { model: "x_ticket", name: "Ticket" },
        ],
      }),
    ).toBe("x_ticket");
  });

  it("accepts string model ids", () => {
    expect(primaryCustomModelFromDraft({ models: ["x_ticket_line", "x_ticket"] })).toBe(
      "x_ticket",
    );
  });

  it("falls back to generation-engine form preview", () => {
    expect(
      primaryCustomModelFromDraft({
        models: [],
        _generation_engine: { form_preview: { model: "x_ticket" } },
      }),
    ).toBe("x_ticket");
  });

  it("returns null when there is no residual model", () => {
    expect(primaryCustomModelFromDraft({ models: [{ model: "sale.order" }] })).toBeNull();
    expect(primaryCustomModelFromDraft(null)).toBeNull();
  });
});

describe("inheritHostModelFromDraft", () => {
  it("picks an inherit host when there is no x_* document", () => {
    expect(
      inheritHostModelFromDraft({
        grain: "field_pack",
        models: [{ model: "account.move", mode: "inherit", fields: [] }],
      }),
    ).toBe("account.move");
  });

  it("falls back to generation-engine form preview", () => {
    expect(
      inheritHostModelFromDraft({
        models: [],
        _generation_engine: { form_preview: { model: "account.move" } },
      }),
    ).toBe("account.move");
  });
});

describe("isFieldPackDraft", () => {
  it("treats inherit-only drafts as field packs", () => {
    expect(
      isFieldPackDraft({
        models: [{ model: "account.move", mode: "inherit" }],
      }),
    ).toBe(true);
    expect(isFieldPackDraft({ grain: "field_pack", models: [] })).toBe(true);
    expect(isFieldPackDraft({ models: [{ model: "x_ticket" }] })).toBe(false);
    expect(
      isFieldPackDraft({
        models: [{ model: "sale.order", mode: "inherit" }],
        _generation_engine: { capability: "option_a_authored" },
      }),
    ).toBe(false);
  });
});

describe("refineSuggestionsFromDraft", () => {
  it("suggests inherit fields instead of add a due date", () => {
    expect(
      refineSuggestionsFromDraft({
        grain: "field_pack",
        models: [
          {
            model: "account.move",
            mode: "inherit",
            fields: [{ name: "x_vendor_tin", string: "Vendor TIN", required: false }],
          },
        ],
      }),
    ).toEqual(["remove Vendor TIN", "make the Vendor TIN field required"]);
  });

  it("does not invent a due date chip", () => {
    expect(refineSuggestionsFromDraft({ models: [] })).toEqual([]);
  });

  it("suggests putting a field next to vendor when it is not already there", () => {
    expect(
      refineSuggestionsFromDraft({
        grain: "field_pack",
        models: [
          {
            model: "account.move",
            mode: "inherit",
            fields: [{ name: "x_vendor_tin", string: "Vendor TIN", required: false }],
          },
        ],
        _form_slots: {
          fields: { x_vendor_tin: "next_to_dates" },
          catalog: [
            { id: "next_to_partner", label: "Next to vendor", phrase: "next to vendor" },
          ],
        },
      }),
    ).toEqual(
      expect.arrayContaining(["put Vendor TIN next to vendor", "remove Vendor TIN"]),
    );
  });
});

describe("inheritPlacementRows", () => {
  it("reads slot stamps for inherit fields", () => {
    expect(
      inheritPlacementRows({
        models: [
          {
            model: "account.move",
            mode: "inherit",
            fields: [{ name: "x_vendor_tin", string: "Vendor TIN" }],
          },
        ],
        _form_slots: { fields: { x_vendor_tin: "next_to_partner" } },
      }),
    ).toEqual([{ name: "x_vendor_tin", string: "Vendor TIN", slot: "next_to_partner" }]);
    expect(
      formSlotCatalog({
        _form_slots: {
          catalog: [{ id: "next_to_partner", label: "Next to vendor", phrase: "next to vendor" }],
        },
      }),
    ).toEqual([{ id: "next_to_partner", label: "Next to vendor", phrase: "next to vendor" }]);
  });
});

describe("viewDesignerHref", () => {
  it("appends the primary custom model", () => {
    expect(
      viewDesignerHref("aa8d", { models: [{ model: "x_ticket" }] }),
    ).toBe("/connections/aa8d/designer?model=x_ticket");
  });

  it("appends the inherit host when there is no custom model", () => {
    expect(
      viewDesignerHref("aa8d", {
        models: [{ model: "account.move", mode: "inherit" }],
      }),
    ).toBe("/connections/aa8d/designer?model=account.move");
  });

  it("omits the query when there is no model", () => {
    expect(viewDesignerHref("aa8d", { models: [] })).toBe("/connections/aa8d/designer");
  });
});
