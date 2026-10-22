import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { FieldPalette, groupPaletteFields, paletteTypeGroup } from "./FieldPalette";

afterEach(() => cleanup());

const FIELDS = [
  { name: "x_name", ttype: "char", label: "Name" },
  { name: "x_stage", ttype: "selection", label: "Stage" },
  { name: "x_partner_id", ttype: "many2one", label: "Customer" },
  { name: "x_amount", ttype: "float", label: "Amount" },
  { name: "x_due", ttype: "date", label: "Due" },
  { name: "x_props", ttype: "properties", label: "Props" },
];

describe("FieldPalette type groups (UI-S-12)", () => {
  it("maps Odoo ttypes to palette groups", () => {
    expect(paletteTypeGroup("char")).toBe("text");
    expect(paletteTypeGroup("monetary")).toBe("numbers");
    expect(paletteTypeGroup("boolean")).toBe("choice");
    expect(paletteTypeGroup("datetime")).toBe("dates");
    expect(paletteTypeGroup("many2many")).toBe("relations");
    expect(paletteTypeGroup("image")).toBe("files");
    expect(paletteTypeGroup("properties")).toBe("other");
  });

  it("keeps a stable group order and skips empty groups", () => {
    const groups = groupPaletteFields(FIELDS).map((g) => g.group.id);
    expect(groups).toEqual(["text", "numbers", "choice", "dates", "relations", "other"]);
  });

  it("renders grouped sections with counts and keeps item test ids", () => {
    render(<FieldPalette fields={FIELDS} />);
    const relations = screen.getByTestId("palette-group-relations");
    expect(within(relations).getByText("Relations")).toBeInTheDocument();
    expect(within(relations).getByText("1")).toBeInTheDocument();
    expect(within(relations).getByTestId("palette-field-x_partner_id")).toBeInTheDocument();
    expect(screen.queryByTestId("palette-group-files")).toBeNull();
  });

  it("filters across groups and shows an empty message", () => {
    render(<FieldPalette fields={FIELDS} />);
    const input = screen.getByLabelText("Filter fields");
    fireEvent.change(input, { target: { value: "selection" } });
    expect(screen.getByTestId("palette-field-x_stage")).toBeInTheDocument();
    expect(screen.queryByTestId("palette-group-text")).toBeNull();
    fireEvent.change(input, { target: { value: "nope" } });
    expect(screen.getByText(/No fields match/)).toBeInTheDocument();
  });
});
