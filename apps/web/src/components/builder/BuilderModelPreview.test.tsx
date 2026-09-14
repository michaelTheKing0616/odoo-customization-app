import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { BuilderModelPreview } from "./BuilderModelPreview";
import type { FieldRow } from "@/lib/api";

const fields: FieldRow[] = [
  {
    id: 1,
    name: "x_name",
    field_description: "Name",
    ttype: "char",
    required: true,
    readonly: false,
    relation: null,
    relation_field: null,
    selection: null,
    modules: [],
  } as FieldRow,
  {
    id: 2,
    name: "x_partner_id",
    field_description: "Customer",
    ttype: "many2one",
    required: false,
    readonly: false,
    relation: "res.partner",
    relation_field: null,
    selection: null,
    modules: [],
  } as FieldRow,
];

describe("BuilderModelPreview", () => {
  it("renders form + list teaser and designer link", () => {
    render(
      <BuilderModelPreview
        connectionId="conn-1"
        model="x_demo"
        modelLabel="Demo"
        fields={fields}
        enableMailThread
      />,
    );
    expect(screen.getByTestId("builder-model-preview")).toBeTruthy();
    expect(screen.getByTestId("odoo-form-view")).toBeTruthy();
    expect(screen.getByTestId("odoo-list-view")).toBeTruthy();
    expect(screen.getByTestId("odoo-chatter-stub")).toBeTruthy();
    const link = screen.getByRole("link", { name: /Customize layout in View Designer/i });
    expect(link.getAttribute("href")).toContain("/connections/conn-1/designer");
    expect(link.getAttribute("href")).toContain("model=x_demo");
  });
});
