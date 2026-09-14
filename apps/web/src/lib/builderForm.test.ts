import { describe, expect, it } from "vitest";
import type { FieldRow } from "@/lib/api";
import {
  automationsHref,
  composerSessionState,
  createdFieldNotice,
  createdModelNotice,
  defaultFieldForm,
  defaultModelForm,
  fieldFormFromRow,
  fieldSubmitPayload,
  fieldTypeLabel,
  filterByQuery,
  isComposerDirty,
  isCustomTechnicalName,
  needsCurrency,
  needsOnDelete,
  needsRelation,
  needsSelection,
  slugifyTechnical,
  viewDesignerHref,
} from "./builderForm";

describe("slugifyTechnical", () => {
  it("prefixes x_ and slugs labels", () => {
    expect(slugifyTechnical("Project Ticket")).toBe("x_project_ticket");
    expect(slugifyTechnical("x_already")).toBe("x_already");
    expect(slugifyTechnical("  ")).toBe("x_custom");
  });
});

describe("composerSessionState", () => {
  it("maps dirty / savedOnce to chrome states", () => {
    expect(composerSessionState({ dirty: true, savedOnce: false })).toBe("unsaved");
    expect(composerSessionState({ dirty: true, savedOnce: true })).toBe("unsaved");
    expect(composerSessionState({ dirty: false, savedOnce: true })).toBe("saved");
    expect(composerSessionState({ dirty: false, savedOnce: false })).toBe("draft");
  });
});

describe("field type gates", () => {
  it("classifies relation, selection, currency, and on_delete", () => {
    expect(needsRelation("many2one")).toBe(true);
    expect(needsRelation("char")).toBe(false);
    expect(needsOnDelete("many2one")).toBe(true);
    expect(needsOnDelete("many2many")).toBe(false);
    expect(needsSelection("selection")).toBe(true);
    expect(needsCurrency("monetary")).toBe(true);
    expect(fieldTypeLabel("many2one")).toBe("Many to one");
    expect(fieldTypeLabel("unknown")).toBe("unknown");
  });
});

describe("isComposerDirty", () => {
  it("detects form vs baseline", () => {
    const a = defaultModelForm();
    const b = defaultModelForm();
    expect(isComposerDirty(a, b)).toBe(false);
    b.name = "Ticket";
    expect(isComposerDirty(a, b)).toBe(true);
  });
});

describe("filterByQuery", () => {
  it("matches haystack case-insensitively", () => {
    const rows = [
      { model: "x_ticket", name: "Ticket" },
      { model: "x_loan", name: "Loan" },
    ];
    expect(filterByQuery(rows, "TICK", (r) => `${r.name} ${r.model}`)).toEqual([rows[0]]);
    expect(filterByQuery(rows, "  ", (r) => r.name)).toEqual(rows);
  });
});

describe("hrefs", () => {
  it("encodes model query for Designer and Automations", () => {
    expect(viewDesignerHref("c1", "x_ticket")).toBe(
      "/connections/c1/designer?model=x_ticket",
    );
    expect(automationsHref("c1", "res.partner")).toBe(
      "/connections/c1/automations?model=res.partner",
    );
    expect(viewDesignerHref("c1", "  ")).toBe("/connections/c1/designer");
  });
});

describe("fieldFormFromRow / submit payload", () => {
  it("hydrates edit form and serializes selection", () => {
    const row = {
      id: 9,
      name: "x_status",
      field_description: "Status",
      ttype: "selection",
      required: true,
      readonly: false,
      relation: null,
      relation_field: null,
      help: "Lifecycle",
      selection: "[('draft','Draft'),('done','Done')]",
      related: null,
      tracking: true,
    } as FieldRow;
    const form = fieldFormFromRow(row, "x_ticket");
    expect(form.model).toBe("x_ticket");
    expect(form.required).toBe(true);
    expect(form.selectionRows[0]).toEqual({ value: "draft", label: "Draft" });
    const payload = fieldSubmitPayload(form);
    expect(payload.selection).toEqual([
      { value: "draft", label: "Draft" },
      { value: "done", label: "Done" },
    ]);
  });
});

describe("notices", () => {
  it("describes model and field success without exclamation marks", () => {
    expect(createdModelNotice({ model: "x_ticket", mailRequested: false })).toMatch(
      /default list\/form\/search/,
    );
    expect(
      createdFieldNotice({
        name: "x_note",
        model: "x_ticket",
        wantedInject: true,
      }),
    ).toMatch(/no existing form\/list\/search/);
    expect(isCustomTechnicalName("x_note")).toBe(true);
    expect(isCustomTechnicalName("name")).toBe(false);
    expect(defaultFieldForm("x_ticket").model).toBe("x_ticket");
  });
});
